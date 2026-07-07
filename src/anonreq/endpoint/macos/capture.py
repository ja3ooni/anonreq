"""macOS traffic capture — packet/network flow monitoring for AI provider traffic.

Uses the discovery hostname matcher to filter traffic to/from known AI providers
and emits metadata-only audit events (no raw traffic content).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class TrafficCapture:
    """Captures and filters network traffic for AI provider detection.

    On macOS, this wraps Npcap/pcap-based packet capture. The base
    implementation provides the interface contract; platform-specific
    capture is activated when pcap bindings are available.

    Args:
        interface: Network interface name (default: "en0").
        matcher: Optional HostnameMatcher instance. Creates one if not provided.
        audit_logger: Optional logger for audit events (must implement .info()).
    """

    def __init__(
        self,
        interface: str = "en0",
        matcher: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.interface = interface
        self.running = False
        self._matcher = matcher
        self._audit_logger = audit_logger

        if self._matcher is None:
            from anonreq.endpoint.discovery import HostnameMatcher

            self._matcher = HostnameMatcher()

    async def start(self) -> None:
        """Start traffic capture.

        If already running, this is a safe no-op.
        """
        if self.running:
            return

        self.running = True
        self._emit_audit("endpoint_capture_started", interface=self.interface)
        logger.info("Traffic capture started on interface %s", self.interface)

    async def stop(self) -> None:
        """Stop traffic capture.

        If already stopped, this is a safe no-op.
        """
        if not self.running:
            return

        self.running = False
        self._emit_audit("endpoint_capture_stopped", interface=self.interface)
        logger.info("Traffic capture stopped on interface %s", self.interface)

    def _is_ai_traffic(self, hostname: str) -> bool:
        """Check if a hostname belongs to a known AI provider.

        Uses the HostnameMatcher to identify AI provider traffic.

        Args:
            hostname: The destination hostname to check.

        Returns:
            True if the hostname matches a known AI provider.
        """
        if not hostname or not self._matcher:
            return False

        result = self._matcher.match(hostname)
        return result is not None

    def _emit_traffic_event(
        self,
        hostname: str,
        provider: str,
        process_name: str = "",
        pid: int = 0,
    ) -> None:
        """Emit an ai_traffic_observed audit event.

        Metadata only — no raw request/response content, no payload,
        no PII. This ensures fail-secure compliance with data
        minimization requirements.

        Args:
            hostname: The destination hostname.
            provider: The matched AI provider name.
            process_name: Optional name of the local process.
            pid: Optional PID of the local process.
        """
        if self._audit_logger is None:
            return

        self._audit_logger.info(
            "ai_traffic_observed",
            hostname=hostname,
            provider=provider,
            process_name=process_name,
            pid=pid,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _emit_audit(self, event_type: str, **fields: Any) -> None:
        """Emit a generic audit event.

        Args:
            event_type: The audit event type string.
            **fields: Additional event fields (metadata only).
        """
        if self._audit_logger is None:
            return

        self._audit_logger.info(
            event_type,
            **fields,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
