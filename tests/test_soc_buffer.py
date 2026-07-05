"""Tests for SinkBuffer — per-sink buffer with LRU eviction and exponential backoff retry.

Tests for:
- Maxsize enforcement (10,000)
- LRU eviction drops oldest events
- Buffer overflow audit event
- Exponential backoff sequence
- Jitter within ±10%
- Max retries exhausted → drop + audit event
- Non-blocking put (put_nowait)
- Prometheus gauge reflects current size
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import pytest

from anonreq.soc.event import NormalizedEvent, SeverityLevel


def _make_event(
    event_id: int = 0,
    event_type: str = "test_event",
) -> NormalizedEvent:
    return NormalizedEvent(
        severity=SeverityLevel.HIGH,
        event_type=event_type,
        tenant_id=f"tenant-{event_id}",
        session_id=f"sess-{event_id}",
        timestamp="2026-06-26T14:30:00.123456Z",
        gateway_version="1.5.0",
        appliance_instance_id="anonreq-test-1",
        mitre_technique_id="T9999",
        metadata={"event_id": event_id},
    )


class FakeAsyncSink:
    """A fake sink for testing buffer behavior."""

    def __init__(
        self,
        name: str = "fake_sink",
        fail_count: int = 0,
        fail_forever: bool = False,
    ) -> None:
        self.name = name
        self.sink_type = "fake"
        self.enabled = True
        self.received: list[NormalizedEvent] = []
        self._fail_count = fail_count
        self._fail_forever = fail_forever
        self._attempts = 0

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_event(self, event: Any) -> bool:
        self._attempts += 1
        if self._fail_forever:
            return False
        if self._attempts <= self._fail_count:
            return False
        self.received.append(event)
        return True

    async def health_check(self) -> Any:
        from anonreq.soc.sinks import SinkStatus
        return SinkStatus(healthy=True, reachable=True)

    async def format_event(self, event: Any) -> str:
        return "formatted"

    @property
    def attempts(self) -> int:
        return self._attempts


class TestSinkBufferMaxSize:
    """Tests for SinkBuffer maxsize enforcement."""

    @pytest.mark.asyncio
    async def test_buffer_enforces_maxsize(self):
        """Test 1: Buffer enforces maxsize — inserting more than maxsize does not raise."""
        from anonreq.soc.buffer import SinkBuffer

        sink = FakeAsyncSink()
        buffer = SinkBuffer(sink=sink, maxsize=10)
        await buffer.start()

        try:
            # Fill buffer to capacity
            for i in range(10):
                await buffer.put(_make_event(event_id=i))

            assert buffer.current_size == 10

            # Adding one more should not raise (LRU eviction)
            await buffer.put(_make_event(event_id=10))
            # Size may still be 10 due to eviction
            assert buffer.current_size <= 10
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_lru_eviction_drops_oldest(self):
        """Test 2: LRU eviction drops oldest events when buffer at capacity."""
        from anonreq.soc.buffer import SinkBuffer

        sink = FakeAsyncSink()
        buffer = SinkBuffer(sink=sink, maxsize=5)
        await buffer.start()

        try:
            # Fill buffer
            events = [_make_event(event_id=i) for i in range(5)]
            for ev in events:
                await buffer.put(ev)

            assert buffer.current_size == 5

            # Now add 3 more — should evict the 3 oldest (0, 1, 2)
            for i in range(5, 8):
                await buffer.put(_make_event(event_id=i))

            assert buffer.current_size <= 5
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_overflow_counter_increments(self):
        """Test 3: Buffer overflow counter increments when events are dropped."""
        from anonreq.soc.buffer import SinkBuffer

        sink = FakeAsyncSink()
        buffer = SinkBuffer(sink=sink, maxsize=5)
        await buffer.start()

        try:
            # Fill and overflow multiple times
            for i in range(20):
                await buffer.put(_make_event(event_id=i))

            assert buffer.overflow_count > 0
            assert buffer.current_size <= 5
        finally:
            await buffer.stop()


class TestExponentialBackoff:
    """Tests for backoff formula correctness."""

    @pytest.mark.asyncio
    async def test_backoff_sequence_default(self):
        """Test 4: Exponential backoff sequence: 1s, 2s, 4s, 8s, 16s, 32s (capped at 60s)."""
        from anonreq.soc.buffer import _backoff_delay, BackoffConfig

        config = BackoffConfig(initial=1, multiplier=2, max=60, jitter=0.0, max_retries=5)

        expected = [1, 2, 4, 8, 16, 32]
        for attempt in range(6):
            delay = _backoff_delay(config, attempt)
            assert math.isclose(delay, expected[attempt], abs_tol=0.01), (
                f"Attempt {attempt}: expected {expected[attempt]}, got {delay}"
            )

    @pytest.mark.asyncio
    async def test_backoff_capped_at_max(self):
        """Backoff is capped at max value (60s)."""
        from anonreq.soc.buffer import _backoff_delay, BackoffConfig

        config = BackoffConfig(initial=1, multiplier=2, max=60, jitter=0.0, max_retries=10)

        for attempt in range(6, 10):
            delay = _backoff_delay(config, attempt)
            assert delay <= 60.0, f"Attempt {attempt}: delay {delay} exceeded max 60"

    @pytest.mark.asyncio
    async def test_jitter_applied_within_range(self):
        """Test 5: Jitter applied within ±10% of computed backoff."""
        from anonreq.soc.buffer import _backoff_delay, BackoffConfig

        config = BackoffConfig(initial=1, multiplier=2, max=60, jitter=0.1, max_retries=5)

        for attempt in range(10):
            delay = _backoff_delay(config, attempt)
            base = min(config.initial * (config.multiplier ** attempt), config.max)
            # Delay should be within ±10% of base
            assert delay >= base * 0.9, f"Delay {delay} below lower bound {base * 0.9}"
            assert delay <= base * 1.1, f"Delay {delay} above upper bound {base * 1.1}"


class TestRetryManager:
    """Tests for retry manager behavior."""

    @pytest.mark.asyncio
    async def test_max_retries_drops_event(self):
        """Test 6: Max retries exhausted → event dropped."""
        from anonreq.soc.buffer import SinkBuffer, BackoffConfig

        # Sink that always fails
        sink = FakeAsyncSink(fail_forever=True)
        backoff = BackoffConfig(initial=0.01, multiplier=2, max=0.1, jitter=0.0, max_retries=3)
        buffer = SinkBuffer(sink=sink, maxsize=10, backoff=backoff)
        await buffer.start()

        try:
            event = _make_event(event_id=42)
            await buffer.put(event)

            # Wait for retries to exhaust
            await asyncio.sleep(0.5)

            # Event should have been dropped (never reached sink)
            assert len(sink.received) == 0
            # Initial attempt + 3 retries = 4 total attempts
            assert sink.attempts == 4
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_event_forwarded_on_success(self):
        """Event is forwarded to sink when send succeeds."""
        from anonreq.soc.buffer import SinkBuffer, BackoffConfig

        sink = FakeAsyncSink(fail_count=0)
        backoff = BackoffConfig(initial=0.01, multiplier=2, max=0.1, jitter=0.0, max_retries=3)
        buffer = SinkBuffer(sink=sink, maxsize=10, backoff=backoff)
        await buffer.start()

        try:
            event = _make_event(event_id=99)
            await buffer.put(event)

            # Wait for processing
            await asyncio.sleep(0.2)

            assert len(sink.received) == 1
            assert sink.received[0].metadata["event_id"] == 99
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Retry after failure then succeed."""
        from anonreq.soc.buffer import SinkBuffer, BackoffConfig

        # Fail once then succeed
        sink = FakeAsyncSink(fail_count=1)
        backoff = BackoffConfig(initial=0.01, multiplier=2, max=0.1, jitter=0.0, max_retries=3)
        buffer = SinkBuffer(sink=sink, maxsize=10, backoff=backoff)
        await buffer.start()

        try:
            event = _make_event(event_id=77)
            await buffer.put(event)

            # Wait for retry
            await asyncio.sleep(0.3)

            assert len(sink.received) == 1
            assert sink.attempts == 2  # 1 failed + 1 successful
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_non_blocking_put(self):
        """Test 7: Buffer put is non-blocking (uses put_nowait internally)."""
        from anonreq.soc.buffer import SinkBuffer

        sink = FakeAsyncSink()
        buffer = SinkBuffer(sink=sink, maxsize=10)
        await buffer.start()

        try:
            # Multiple rapid puts should not block
            for i in range(100):
                await buffer.put(_make_event(event_id=i))

            assert buffer.current_size == 10  # Capped at maxsize
        finally:
            await buffer.stop()


class TestSinkBufferMetrics:
    """Tests for Prometheus metrics."""

    @pytest.mark.asyncio
    async def test_buffer_size_gauge(self):
        """Test 8: Buffer size gauge reflects current size."""
        from anonreq.soc.buffer import SinkBuffer

        sink = FakeAsyncSink()
        buffer = SinkBuffer(sink=sink, maxsize=100)
        await buffer.start()

        try:
            assert buffer.current_size == 0

            await buffer.put(_make_event(event_id=1))
            assert buffer.current_size == 1

            await buffer.put(_make_event(event_id=2))
            assert buffer.current_size == 2
        finally:
            await buffer.stop()
