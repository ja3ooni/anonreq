"""SinkRouter — fan-out normalized events to all registered SIEM sinks.

Routes normalized events from the SOCNormalizer to all enabled sinks.
Each sink runs independently — a failure in one does not affect others.
"""

from __future__ import annotations

import logging
from typing import Any

from anonreq.soc.sinks import SinkBase, SinkStatus

logger = logging.getLogger("anonreq.soc.router")


class SinkRouter:
    """Routes normalized events to all registered sink instances.

    Provides lifecycle management (start/stop) for all sinks and
    fan-out delivery. Sinks can be registered at startup from config.

    Each sink runs independently — send errors are logged but do not
    propagate to other sinks or the normalizer.
    """

    def __init__(self) -> None:
        self._sinks: dict[str, SinkBase] = {}

    def register(self, sink: SinkBase) -> None:
        """Register a sink instance.

        Args:
            sink: A ``SinkBase``-compatible instance.
        """
        self._sinks[sink.name] = sink
        logger.info(
            "Sink registered",
            extra={"sink_name": sink.name, "sink_type": sink.sink_type},
        )

    async def fan_out(self, event: Any) -> None:
        """Deliver a normalized event to all enabled sinks.

        Args:
            event: A ``NormalizedEvent`` to distribute.
        """
        for sink_name, sink in self._sinks.items():
            if not sink.enabled:
                continue
            try:
                await sink.send_event(event)
            except Exception:
                logger.exception(
                    "Sink send failed for '%s'",
                    sink_name,
                    extra={"sink_name": sink_name, "event_type": getattr(event, "event_type", "unknown")},  # noqa: E501
                )

    def get_sinks(self) -> dict[str, SinkBase]:
        """Return all registered sink instances.

        Returns:
            Dict mapping sink name to ``SinkBase`` instances.
        """
        return dict(self._sinks)

    def get_sink_statuses(self) -> dict[str, SinkStatus]:
        """Return status dict for all registered sinks.

        Returns:
            Dict mapping sink name to ``SinkStatus``. For sinks that
            haven't been probed yet, returns a default SinkStatus.
        """
        result: dict[str, SinkStatus] = {}
        for sink_name, sink in self._sinks.items():
            try:
                result[sink_name] = SinkStatus(
                    healthy=sink.enabled,
                    reachable=True,
                    buffer_size=0,
                )
            except Exception:
                result[sink_name] = SinkStatus(
                    healthy=False, reachable=False, last_error="Unknown"
                )
        return result

    @property
    def sinks(self) -> dict[str, SinkBase]:
        """Return all registered sink instances."""
        return dict(self._sinks)

    async def start_all(self) -> None:
        """Call start() on all registered sinks."""
        for sink_name, sink in self._sinks.items():
            if not sink.enabled:
                continue
            try:
                await sink.start()
                logger.info(
                    "Sink started",
                    extra={"sink_name": sink_name},
                )
            except Exception:
                logger.exception(
                    "Failed to start sink '%s'",
                    sink_name,
                )

    async def stop_all(self) -> None:
        """Call stop() on all registered sinks."""
        for sink_name, sink in self._sinks.items():
            try:
                await sink.stop()
                logger.info(
                    "Sink stopped",
                    extra={"sink_name": sink_name},
                )
            except Exception:
                logger.exception(
                    "Failed to stop sink '%s'",
                    sink_name,
                )
