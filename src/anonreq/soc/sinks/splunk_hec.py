"""Splunk HEC (HTTP Event Collector) SIEM sink.

Per D-005 and 20-ARCHITECTURE.md:
- Formats normalized events as HEC JSON envelopes
- POSTs to ``/services/collector/event`` with ``Authorization: Splunk {token}``
- Sourcetype: ``anonreq:ai_security``
- Supports batch sends and health checks
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from prometheus_client import Counter

from anonreq.soc.sinks import SinkBase, SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.splunk_hec")

splunk_events_total = Counter(
    "anonreq_soc_sink_splunk_hec_total",
    "Events sent to Splunk HEC sink",
    ["sink_name"],
)


class SplunkHECSink:
    """Splunk HEC sink — sends normalized events to Splunk HEC endpoint.

    Formats events as HEC envelopes with ``sourcetype: anonreq:ai_security``
    and authenticates via ``Authorization: Splunk {token}`` header.

    Args:
        name: Human-readable sink instance name.
        endpoint: Full Splunk HEC URL (e.g.
            ``https://splunk-instance:8088/services/collector/event``).
        token: Splunk HEC authentication token.
        tls_verify: Whether to verify TLS certificates (default True).
        timeout: HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
        token: str,
        tls_verify: bool = True,
        timeout: int = 30,
    ) -> None:
        self.name = name
        self.sink_type = "splunk_hec"
        self.enabled = True
        self._endpoint = endpoint
        self._token = token
        self._tls_verify = tls_verify
        self._timeout = timeout
        self._auth_header = f"Splunk {token}"
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Create the HTTPX async client."""
        self._client = httpx.AsyncClient(
            verify=self._tls_verify,
            timeout=httpx.Timeout(self._timeout),
        )

    async def stop(self) -> None:
        """Close the HTTPX async client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def format_event(self, event: Any) -> dict:
        """Format a NormalizedEvent into a Splunk HEC envelope.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            HEC envelope dict with time, host, source, sourcetype, event fields.
        """
        return {
            "time": self._timestamp_to_unix(event.timestamp),
            "host": event.appliance_instance_id,
            "source": "anonreq",
            "sourcetype": "anonreq:ai_security",
            "event": {
                "severity": event.severity.value,
                "event_type": event.event_type,
                "tenant_id": event.tenant_id,
                "session_id": event.session_id,
                "gateway_version": event.gateway_version,
                "appliance_instance_id": event.appliance_instance_id,
                "mitre_technique_id": event.mitre_technique_id,
                "metadata": event.metadata,
            },
        }

    async def send_event(self, event: Any) -> bool:
        """Send a single event to Splunk HEC.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful (HTTP 2xx), False otherwise.
        """
        if self._client is None:
            return False

        try:
            envelope = await self.format_event(event)
            response = await self._client.post(
                self._endpoint,
                json=envelope,
                headers={
                    "Authorization": self._auth_header,
                    "Content-Type": "application/json",
                },
            )
            if response.is_success:
                splunk_events_total.labels(sink_name=self.name).inc()
                return True

            logger.warning(
                "Splunk HEC send failed with status %d",
                response.status_code,
                extra={
                    "sink_name": self.name,
                    "status_code": response.status_code,
                    "event_type": event.event_type,
                },
            )
            return False
        except Exception as exc:
            logger.warning(
                "Splunk HEC send error: %s",
                str(exc),
                extra={"sink_name": self.name, "event_type": event.event_type},
            )
            return False

    async def send_batch(self, events: list[Any]) -> bool:
        """Send multiple events in a single HEC request.

        Args:
            events: List of ``NormalizedEvent`` instances.

        Returns:
            True if delivery was successful, False otherwise.
        """
        if self._client is None or not events:
            return False

        try:
            envelopes = [await self.format_event(ev) for ev in events]
            response = await self._client.post(
                self._endpoint,
                json=envelopes,
                headers={
                    "Authorization": self._auth_header,
                    "Content-Type": "application/json",
                },
            )
            if response.is_success:
                splunk_events_total.labels(sink_name=self.name).inc(len(events))
                return True
            return False
        except Exception as exc:
            logger.warning(
                "Splunk HEC batch send error: %s",
                str(exc),
                extra={"sink_name": self.name},
            )
            return False

    async def health_check(self) -> SinkStatus:
        """Check Splunk HEC endpoint reachability.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        if self._client is None:
            return SinkStatus(healthy=False, reachable=False, last_error="Client not started")

        try:
            # Try the health endpoint
            health_url = self._endpoint.replace(
                "services/collector/event", "services/collector/health"
            )
            response = await self._client.get(health_url)
            if response.is_success:
                return SinkStatus(healthy=True, reachable=True)
            return SinkStatus(
                healthy=False,
                reachable=False,
                last_error=f"Health check returned {response.status_code}",
            )
        except Exception as exc:
            return SinkStatus(
                healthy=False,
                reachable=False,
                last_error=str(exc),
            )

    @staticmethod
    def _timestamp_to_unix(iso_timestamp: str) -> float:
        """Convert an ISO 8601 timestamp string to a Unix timestamp float.

        Args:
            iso_timestamp: ISO 8601 formatted timestamp string.

        Returns:
            Unix timestamp as float with microsecond precision.
        """
        try:
            dt = datetime.fromisoformat(iso_timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except (ValueError, TypeError):
            return datetime.now(timezone.utc).timestamp()
