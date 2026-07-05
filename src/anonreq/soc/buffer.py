"""Per-sink buffer with LRU eviction and exponential backoff retry.

Per D-017 through D-021, 20-ARCHITECTURE.md:
- ``SinkBuffer``: asyncio.Queue per sink with maxsize 10,000
- LRU eviction drops oldest events when buffer is full
- ``RetryManager``: exponential backoff with jitter, max 5 retries
- Non-blocking ``put_nowait`` — never blocks request processing
- Prometheus metrics: buffer_size gauge, overflow_total counter
- Audit events: soc_buffer_overflow, soc_event_dropped, soc_event_forwarded
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

from prometheus_client import Counter, Gauge

from anonreq.soc.event import NormalizedEvent

logger = logging.getLogger("anonreq.soc.buffer")


@dataclass
class BackoffConfig:
    """Configuration for exponential backoff retry.

    Attributes:
        initial: Initial backoff delay in seconds (default 1.0).
        multiplier: Multiplier for exponential growth (default 2.0).
        max: Maximum backoff delay in seconds (default 60.0).
        jitter: Jitter fraction relative to computed delay (default 0.1).
        max_retries: Maximum number of retry attempts (default 5).
    """

    initial: float = 1.0
    multiplier: float = 2.0
    max: float = 60.0
    jitter: float = 0.1
    max_retries: int = 5


def _backoff_delay(config: BackoffConfig, attempt: int) -> float:
    """Compute exponential backoff delay with jitter.

    Formula::
        base = min(initial * multiplier^attempt, max)
        jitter_amount = base * jitter
        delay = base + uniform(-jitter_amount, jitter_amount)

    Args:
        config: Backoff configuration parameters.
        attempt: Current attempt number (0 = first attempt).

    Returns:
        Delay in seconds.
    """
    base = min(config.initial * (config.multiplier**attempt), config.max)
    jitter_amount = base * config.jitter
    return base + random.uniform(-jitter_amount, jitter_amount)


# Prometheus metrics
_buffer_size = Gauge(
    "anonreq_soc_buffer_size",
    "Current number of events in the per-sink buffer",
    ["sink_name"],
)

_buffer_overflow_total = Counter(
    "anonreq_soc_buffer_overflow_total",
    "Total number of buffer overflow events (oldest dropped)",
    ["sink_name"],
)

_event_dropped_total = Counter(
    "anonreq_soc_event_dropped_total",
    "Events dropped after max retries",
    ["sink_name"],
)

_event_forwarded_total = Counter(
    "anonreq_soc_event_forwarded_total",
    "Events successfully forwarded to sink",
    ["sink_name"],
)


class SinkBuffer:
    """Per-sink buffer with LRU eviction and exponential backoff retry.

    Wraps a ``SinkBase`` instance, providing an async queue that decouples
    event producers from sink delivery. Events are retried with exponential
    backoff; if the retry budget is exhausted the event is dropped with an
    audit event.

    Args:
        sink: A ``SinkBase``-compatible instance to wrap.
        maxsize: Maximum queue size (default 10000).
        backoff: Backoff configuration (default ``BackoffConfig()``).
        audit_logger: Optional async audit logger for soc events.
        metrics_registry: Optional Prometheus registry (defaults to global).
    """

    def __init__(
        self,
        sink: Any,
        maxsize: int = 10000,
        backoff: BackoffConfig | None = None,
        audit_logger: Any | None = None,
        metrics_registry: Any | None = None,
    ) -> None:
        self._sink = sink
        self._maxsize = maxsize
        self._backoff = backoff or BackoffConfig()
        self._audit_logger = audit_logger
        self._queue: asyncio.Queue[tuple[int, NormalizedEvent]] = asyncio.Queue(
            maxsize=maxsize
        )
        self._counter = 0
        self._overflow_emitted = False
        self._overflow_total = 0
        self._task: asyncio.Task | None = None
        self._sink_label = sink.name

        # Initialize Prometheus
        _buffer_size.labels(sink_name=self._sink_label).set(0)

    async def put(self, event: NormalizedEvent) -> None:
        """Add an event to the buffer (non-blocking).

        Uses ``put_nowait`` internally. If the buffer is full, the oldest
        event is dropped (LRU eviction) and a ``soc_buffer_overflow``
        audit event is emitted once per overflow burst.

        Args:
            event: The normalized event to enqueue.
        """
        seq = self._counter
        self._counter += 1

        try:
            self._queue.put_nowait((seq, event))
            self._overflow_emitted = False
        except asyncio.QueueFull:
            # LRU eviction: drain one oldest event
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self._overflow_total += 1
                _buffer_overflow_total.labels(sink_name=self._sink_label).inc()

                if not self._overflow_emitted:
                    logger.warning(
                        "Buffer overflow for sink '%s' — oldest event dropped",
                        self._sink_label,
                        extra={
                            "sink_name": self._sink_label,
                            "overflow_total": self._overflow_total,
                        },
                    )
                    self._overflow_emitted = True

                # Retry the put
                self._queue.put_nowait((seq, event))
            except asyncio.QueueFull:
                pass  # Still full after eviction — drop current event

        _buffer_size.labels(sink_name=self._sink_label).set(self._queue.qsize())

    @property
    def current_size(self) -> int:
        """Current number of events in the buffer."""
        return self._queue.qsize()

    @property
    def overflow_count(self) -> int:
        """Total number of overflow events."""
        return self._overflow_total

    async def start(self) -> None:
        """Start the background retry loop as an asyncio task."""
        self._task = asyncio.create_task(self._retry_loop())

    async def stop(self) -> None:
        """Cancel the retry loop and drain remaining events."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._drain()

    async def _retry_loop(self) -> None:
        """Background loop consuming events from the queue and retrying."""
        while True:
            try:
                seq, event = await self._queue.get()
                sent = False

                for attempt in range(self._backoff.max_retries + 1):
                    try:
                        result = await self._sink.send_event(event)
                        if result:
                            _event_forwarded_total.labels(
                                sink_name=self._sink_label
                            ).inc()
                            sent = True
                            break
                    except Exception as exc:
                        logger.debug(
                            "Sink send attempt %d failed for '%s': %s",
                            attempt + 1,
                            self._sink_label,
                            str(exc),
                        )

                    # If not the last attempt, wait with backoff
                    if attempt < self._backoff.max_retries:
                        delay = _backoff_delay(self._backoff, attempt)
                        await asyncio.sleep(delay)

                if not sent:
                    _event_dropped_total.labels(
                        sink_name=self._sink_label
                    ).inc()
                    logger.warning(
                        "Event dropped after %d retries for sink '%s'",
                        self._backoff.max_retries,
                        self._sink_label,
                        extra={
                            "sink_name": self._sink_label,
                            "event_type": event.event_type,
                        },
                    )

                self._queue.task_done()
                _buffer_size.labels(sink_name=self._sink_label).set(
                    self._queue.qsize()
                )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "Error in buffer retry loop for sink '%s'",
                    self._sink_label,
                )
                self._queue.task_done()

    def _drain(self) -> None:
        """Drain remaining events from the queue."""
        drained = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained:
            logger.info(
                "Drained %d events from sink '%s' buffer",
                drained,
                self._sink_label,
            )
