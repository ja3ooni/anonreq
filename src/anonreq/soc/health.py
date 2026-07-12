"""Periodic sink health monitor.

Per D-022 through D-024, 20-ARCHITECTURE.md:
- ``SinkHealthMonitor`` probes each enabled sink at a configurable interval
- Maintains a status cache with per-sink ``SinkStatus``
- Emits audit events on reachable/unreachable transitions
- Provides aggregate status (healthy/degraded/unknown)
- Updates Prometheus gauge per sink
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from prometheus_client import Gauge

from anonreq.soc.sinks import SinkStatus

logger = logging.getLogger("anonreq.soc.health")

_sink_healthy = Gauge(
    "anonreq_soc_sink_healthy",
    "Sink health status (1=healthy, 0=unhealthy)",
    ["sink_name"],
)


class SinkHealthMonitor:
    """Periodic health monitor for all registered SIEM sinks.

    Probes each enabled sink at a configurable interval and maintains
    a status cache. Exposes status via ``get_status()`` for API consumption.

    Args:
        router: A ``SinkRouter`` instance (or any object with a
            ``get_sinks()`` method returning a dict of sink name → sink).
        interval: Probe interval in seconds (default 60).
        metrics_registry: Optional Prometheus registry (defaults to global).
    """

    def __init__(
        self,
        router: Any,
        interval: int = 60,
        _metrics_registry: Any | None = None,
    ) -> None:
        self._router = router
        self._interval = interval
        self._tasks: dict[str, asyncio.Task] = {}
        self._status_cache: dict[str, SinkStatus] = {}

    async def start(self) -> None:
        """Start per-sink probe tasks for all enabled sinks."""
        sinks = self._router.get_sinks()
        for sink_name, sink in sinks.items():
            if not getattr(sink, "enabled", True):
                continue
            task = asyncio.create_task(
                self._probe_loop(sink_name, sink)
            )
            self._tasks[sink_name] = task
            logger.info(
                "Health probe started for sink '%s'",
                sink_name,
                extra={"sink_name": sink_name},
            )

    async def stop(self) -> None:
        """Cancel all probe tasks."""
        for _sink_name, task in self._tasks.items():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def _probe_loop(self, sink_name: str, sink: Any) -> None:
        """Background loop that probes a single sink at the configured interval.

        Args:
            sink_name: Name of the sink to probe.
            sink: The sink instance with a ``health_check()`` method.
        """
        while True:
            try:
                status = await sink.health_check()
                previous = self._status_cache.get(sink_name)

                # Track transitions
                if previous is not None:
                    if previous.reachable and not status.reachable:
                        logger.warning(
                            "Sink '%s' became unreachable",
                            sink_name,
                            extra={
                                "sink_name": sink_name,
                                "last_error": status.last_error,
                            },
                        )
                    elif not previous.reachable and status.reachable:
                        logger.info(
                            "Sink '%s' became reachable",
                            sink_name,
                            extra={"sink_name": sink_name},
                        )

                self._status_cache[sink_name] = status
                _sink_healthy.labels(sink_name=sink_name).set(
                    1 if status.reachable else 0
                )

            except Exception as exc:
                logger.error(
                    "Health probe failed for sink '%s': %s",
                    sink_name,
                    str(exc),
                    extra={"sink_name": sink_name},
                )
                # Cache as unhealthy
                self._status_cache[sink_name] = SinkStatus(
                    healthy=False,
                    reachable=False,
                    last_error=str(exc),
                )
                _sink_healthy.labels(sink_name=sink_name).set(0)

            await asyncio.sleep(self._interval)

    def get_status(self) -> dict[str, SinkStatus]:
        """Return the cached health status for all probed enabled sinks.

        Also includes enabled sinks not yet probed by checking the router
        for any registered sinks not in the cache. Disabled sinks are
        excluded from status output.

        Returns:
            Dict mapping sink name to ``SinkStatus``.
        """
        # Include all probed sinks from cache
        result = dict(self._status_cache)

        # Add any enabled sinks we haven't probed yet from the router
        sinks = self._router.get_sinks()
        for sink_name, sink in sinks.items():
            if sink_name in result:
                continue
            # Skip disabled sinks
            if not getattr(sink, "enabled", True):
                continue
            result[sink_name] = SinkStatus(
                healthy=False,
                reachable=False,
                last_error="Not yet probed",
            )

        return result

    def get_aggregate_status(self) -> str:
        """Compute aggregate health status across all enabled sinks.

        Returns:
            ``"healthy"`` if all enabled sinks are reachable.
            ``"degraded"`` if any enabled sink is unreachable.
            ``"unknown"`` if no enabled sinks are registered.
        """
        statuses = self.get_status()
        if not statuses:
            return "unknown"

        all_reachable = all(s.reachable for s in statuses.values())
        if all_reachable:
            return "healthy"
        return "degraded"
