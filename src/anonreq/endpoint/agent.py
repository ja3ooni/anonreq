"""Endpoint Agent — async lifecycle manager for the desktop agent.

Manages discovery, capture, heartbeat, and telemetry as background tasks.
Emits audit events for lifecycle transitions and periodic status.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from datetime import datetime, timezone
from typing import Any

from anonreq.endpoint.config import EndpointConfig, load_config
from anonreq.endpoint.discovery import AppDiscovery

logger = logging.getLogger(__name__)

# Version of the endpoint agent package
__version__ = "0.1.0"


class EndpointAgent:
    """Async lifecycle manager for the endpoint agent.

    Manages background tasks for:
    - AI application discovery (periodic process scanning)
    - Network traffic capture (if enabled)
    - Heartbeat telemetry emission
    - Configuration API (via embedded HTTP server)

    Args:
        config: EndpointConfig instance. Loaded from default paths if None.
        audit_logger: Optional structured logger for audit events.
            Must implement .info(event_type, **fields).
        config_override: Optional dict of config overrides for testing.
    """

    def __init__(
        self,
        config: EndpointConfig | None = None,
        audit_logger: Any = None,
        config_override: dict[str, Any] | None = None,
    ) -> None:
        if config is None:
            config = load_config()

        if config_override:
            for key, value in config_override.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        self.config = config
        self._audit_logger = audit_logger

        self.running = False
        self._tasks: list[asyncio.Task[Any]] = []
        self._start_time: float = 0.0
        self._traffic_count = 0
        self._hostname = platform.node()
        self._version = __version__
        self._pii_safe_fields = True  # Track that agent follows PII-safe patterns

        # Sub-components
        self._discovery = AppDiscovery(audit_logger=audit_logger)

        self._capture = None
        if self.config.capture_enabled:
            from anonreq.endpoint.macos.capture import TrafficCapture

            self._capture = TrafficCapture(
                interface=self.config.capture_interface,
                audit_logger=audit_logger,
            )

    @property
    def uptime_seconds(self) -> float:
        """Seconds since agent started."""
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    async def start(self) -> None:
        """Start the endpoint agent and background tasks.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self.running:
            return

        self.running = True
        self._start_time = time.time()

        self._emit_audit(
            "endpoint_agent_started",
            hostname=self._hostname,
            version=self._version,
        )

        # Start background tasks
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        self._tasks.append(asyncio.create_task(self._discovery_loop()))

        if self._capture:
            await self._capture.start()

        logger.info(
            "Endpoint agent started on %s (v%s)",
            self._hostname,
            self._version,
        )

    async def stop(self) -> None:
        """Stop the endpoint agent and cancel background tasks.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if not self.running:
            return

        self.running = False
        uptime = self.uptime_seconds

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        if self._capture:
            await self._capture.stop()

        self._emit_audit(
            "endpoint_agent_stopped",
            uptime_seconds=round(uptime, 2),
        )

        logger.info(
            "Endpoint agent stopped (uptime: %.2fs)",
            uptime,
        )

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat telemetry emission."""
        while self.running:
            await self._send_heartbeat()
            await asyncio.sleep(self.config.heartbeat_interval_sec)

    async def _discovery_loop(self) -> None:
        """Periodic AI application discovery scan."""
        while self.running:
            self._run_discovery()
            await asyncio.sleep(self.config.discovery_interval_sec)

    def _run_discovery(self) -> list[dict[str, Any]]:
        """Run one discovery scan cycle.

        Returns:
            List of discovered app dicts.
        """
        return self._discovery.discover_and_emit()

    async def _send_heartbeat(self) -> None:
        """Emit heartbeat telemetry event."""
        if self._audit_logger is None:
            return

        apps = self._run_discovery()

        self._audit_logger.info(
            "endpoint_agent_heartbeat",
            uptime_seconds=round(self.uptime_seconds, 2),
            discovered_apps=len(apps),
            captured_traffic_count=self._traffic_count,
            status="running" if self.running else "stopped",
            hostname=self._hostname,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _emit_audit(self, event_type: str, **fields: Any) -> None:
        """Emit an audit event.

        Args:
            event_type: The event type string.
            **fields: Event fields (metadata only, no PII).
        """
        if self._audit_logger is None:
            return

        self._audit_logger.info(event_type, **fields)
