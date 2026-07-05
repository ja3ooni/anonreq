"""QRadar CEF (Common Event Format) SIEM sink.

Per D-005 and 20-ARCHITECTURE.md:
- Formats normalized events as CEF:0|AnonReq|Appliance|{version}|{sig}|{name}|{sev}
- Sends over TCP (default) or UDP syslog to QRadar SIEM
- Extension fields use ArcSight-style key=value pairs
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from prometheus_client import Counter

from anonreq.soc.event import SeverityLevel
from anonreq.soc.sinks import SinkBase, SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.qradar_cef")

qradar_events_total = Counter(
    "anonreq_soc_sink_qradar_cef_total",
    "Events sent to QRadar CEF sink",
    ["sink_name"],
)

# CEF severity mapping: NormalizedEvent severity → 1-10
_SEVERITY_MAP: dict[SeverityLevel, int] = {
    SeverityLevel.CRITICAL: 10,
    SeverityLevel.HIGH: 8,
    SeverityLevel.MEDIUM: 5,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFORMATIONAL: 1,
}


class QRadarCEFSink:
    """QRadar CEF sink — sends normalized events as syslog CEF messages.

    Formats events as CEF:0|AnonReq|Appliance|{version}|{sig_id}|{name}|{sev}
    with key=value extension fields.

    Args:
        name: Human-readable sink instance name.
        host: QRadar syslog collector hostname or IP.
        port: QRadar syslog collector port (default 514 for TCP, 514 for UDP).
        use_tcp: Send over TCP (True) or UDP (False). Default True.
        source_host: Hostname to include in CEF extension fields.
    """

    def __init__(
        self,
        name: str,
        host: str,
        port: int = 514,
        use_tcp: bool = True,
        source_host: str | None = None,
    ) -> None:
        self.name = name
        self.sink_type = "qradar_cef"
        self.enabled = True
        self._host = host
        self._port = port
        self._use_tcp = use_tcp
        self._source_host = source_host or ""
        self._writer: asyncio.StreamWriter | None = None

    async def start(self) -> None:
        """Open the TCP/UDP connection (lazy open on first send for TCP)."""
        if self._use_tcp:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=5,
                )
                self._writer = writer
            except (OSError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "QRadar CEF sink start: connection to %s:%d failed: %s",
                    self._host,
                    self._port,
                    str(exc),
                )
                self._writer = None

    async def stop(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

    async def format_event(self, event: Any) -> str:
        """Format a NormalizedEvent into a CEF syslog string.

        Returns a CEF-formatted string:
            CEF:0|AnonReq|Appliance|{version}|{sig_id}|{name}|{sev}| {extensions}

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            CEF-formatted syslog string.
        """
        sig_id = event.mitre_technique_id or "0"
        cef_severity = _SEVERITY_MAP.get(event.severity, 1)
        # Sanitize event name (no pipes in CEF field #6)
        event_name = event.event_type.replace("|", "/")

        extension_parts = [
            f"tenantId={event.tenant_id}",
            f"sessionId={event.session_id}",
            f"gatewayVersion={event.gateway_version}",
            f"applianceId={event.appliance_instance_id}",
        ]

        if event.mitre_technique_id:
            extension_parts.append(f"mitreTechniqueId={event.mitre_technique_id}")
        if self._source_host:
            extension_parts.append(f"src={self._source_host}")

        # Add metadata fields
        for key, value in (event.metadata or {}).items():
            # ArcSight extension keys use camelCase
            cef_key = _to_cef_extension_key(key)
            cef_value = _sanitize_cef_value(str(value))
            extension_parts.append(f"{cef_key}={cef_value}")

        cef_header = (
            f"CEF:0|AnonReq|Appliance|{event.gateway_version}|"
            f"{sig_id}|{event_name}|{cef_severity}"
        )
        return f"{cef_header} {' '.join(extension_parts)}"

    async def send_event(self, event: Any) -> bool:
        """Send a CEF event to QRadar.

        For TCP: ensures connection is open, writes the CEF line + newline.
        For UDP: uses UDP transport.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful, False otherwise.
        """
        try:
            cef_line = await self.format_event(event)
            return await self._send_line(cef_line)
        except Exception:
            return False

    async def _send_line(self, line: str) -> bool:
        """Send a raw CEF line to the syslog target."""
        if self._use_tcp:
            return await self._send_tcp(line)
        return await self._send_udp(line)

    async def _ensure_connection(self) -> bool:
        """Ensure TCP connection is open, reconnect if needed."""
        if self._writer is not None and not self._writer.is_closing():
            return True
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=5,
            )
            self._writer = writer
            return True
        except (OSError, asyncio.TimeoutError):
            self._writer = None
            return False

    async def _send_tcp(self, line: str) -> bool:
        """Send a CEF line over TCP syslog."""
        connected = await self._ensure_connection()
        if not connected:
            return False

        try:
            self._writer.write((line + "\n").encode("utf-8"))
            await self._writer.drain()
            qradar_events_total.labels(sink_name=self.name).inc()
            return True
        except (OSError, ConnectionError) as exc:
            logger.warning(
                "QRadar TCP send error: %s",
                str(exc),
                extra={"sink_name": self.name},
            )
            self._writer = None
            return False

    async def _send_udp(self, line: str) -> bool:
        """Send a CEF line over UDP syslog."""
        try:
            transport, protocol = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                remote_addr=(self._host, self._port),
            )
            try:
                transport.sendto((line + "\n").encode("utf-8"))
                qradar_events_total.labels(sink_name=self.name).inc()
                return True
            finally:
                transport.close()
        except (OSError, ConnectionError) as exc:
            logger.warning(
                "QRadar UDP send error: %s",
                str(exc),
                extra={"sink_name": self.name},
            )
            return False

    async def health_check(self) -> SinkStatus:
        """Check QRadar syslog collector reachability.

        For TCP: attempts a socket connection to host:port.
        For UDP: checks if a basic socket can be created.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=3,
            )
            writer.close()
            await writer.wait_closed()
            return SinkStatus(healthy=True, reachable=True)
        except (OSError, asyncio.TimeoutError) as exc:
            return SinkStatus(
                healthy=False,
                reachable=False,
                last_error=str(exc),
            )


def _to_cef_extension_key(key: str) -> str:
    """Convert a snake_case metadata key to an ArcSight CEF camelCase key.

    Args:
        key: snake_case key like ``dlp_category``.

    Returns:
        camelCase key like ``dlpCategory``.
    """
    parts = key.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _sanitize_cef_value(value: str) -> str:
    """Sanitize a value string for CEF extension fields.

    Escapes special characters (\\, =, |) and trims whitespace.

    Args:
        value: Raw value string.

    Returns:
        Sanitized string safe for CEF extensions.
    """
    result = value.replace("\\", "\\\\")
    result = result.replace("=", "\\=")
    result = result.replace("|", "\\|")
    return result.strip()
