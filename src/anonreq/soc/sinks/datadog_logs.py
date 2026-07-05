"""Datadog Logs API SIEM sink.

Per D-009 and 20-ARCHITECTURE.md:
- Formats normalized events as Datadog JSON log entries
- POSTs to ``https://http-intake.logs.{site}/api/v2/logs``
- Authorization: ``DD-API-KEY`` header
- Configurable site (datadoghq.com, datadoghq.eu, us3.datadoghq.com, ddog-gov.com)
- Configurable source tag (default: ``anonreq``)
- Supports batch sends
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from prometheus_client import Counter

from anonreq.soc.sinks import SinkBase, SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.datadog_logs")

DATADOG_LOGS_URL = "https://http-intake.logs.{site}/api/v2/logs"
DEFAULT_SOURCE_TAG = "anonreq"

datadog_events_total = Counter(
    "anonreq_soc_sink_datadog_logs_total",
    "Events sent to Datadog Logs sink",
    ["sink_name"],
)


class DatadogLogsSink:
    """Datadog Logs API sink — sends normalized events to Datadog.

    Formats events as Datadog log entries with configurable source,
    tags, and site. Authenticates via ``DD-API-KEY`` header.

    Args:
        name: Human-readable sink instance name.
        api_key: Datadog API key.
        site: Datadog site (default ``datadoghq.com``).
            Supported: ``datadoghq.com``, ``datadoghq.eu``,
            ``us3.datadoghq.com``, ``ddog-gov.com``.
        source_tag: Value for the ``ddsource`` field (default ``anonreq``).
        tls_verify: Whether to verify TLS certificates (default True).
        timeout: HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        site: str = "datadoghq.com",
        source_tag: str = DEFAULT_SOURCE_TAG,
        tls_verify: bool = True,
        timeout: int = 30,
    ) -> None:
        self.name = name
        self.sink_type = "datadog_logs"
        self.enabled = True
        self._api_key = api_key
        self._source_tag = source_tag
        self._tls_verify = tls_verify
        self._timeout = timeout
        self._logs_url = DATADOG_LOGS_URL.format(site=site)
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
        """Format a NormalizedEvent into a Datadog log entry.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            Datadog log entry dict with ddsource, ddtags, hostname,
            service, and message fields.
        """
        return {
            "ddsource": self._source_tag,
            "ddtags": (
                f"env:production,tenant:{event.tenant_id},"
                f"gateway_version:{event.gateway_version}"
            ),
            "hostname": event.appliance_instance_id,
            "service": "anonreq",
            "message": json.dumps({
                "severity": event.severity.value,
                "event_type": event.event_type,
                "session_id": event.session_id,
                "mitre_technique_id": event.mitre_technique_id,
                "metadata": event.metadata,
            }),
        }

    async def send_event(self, event: Any) -> bool:
        """Send a single event to Datadog.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful (HTTP 202), False otherwise.
        """
        if self._client is None:
            return False

        try:
            formatted = await self.format_event(event)
            return await self._post_logs([formatted], 1)
        except Exception as exc:
            logger.warning(
                "Datadog Logs send error: %s",
                str(exc),
                extra={"sink_name": self.name, "event_type": event.event_type},
            )
            return False

    async def send_batch(self, events: list[Any]) -> bool:
        """Send multiple events in a single request.

        Args:
            events: List of ``NormalizedEvent`` instances.

        Returns:
            True if delivery was successful, False otherwise.
        """
        if self._client is None or not events:
            return False

        try:
            formatted = [await self.format_event(ev) for ev in events]
            return await self._post_logs(formatted, len(events))
        except Exception as exc:
            logger.warning(
                "Datadog Logs batch send error: %s",
                str(exc),
                extra={"sink_name": self.name},
            )
            return False

    async def _post_logs(self, entries: list[dict], count: int) -> bool:
        """POST log entries to the Datadog Logs API.

        Args:
            entries: List of formatted log entry dicts.
            count: Number of events for metric counting.

        Returns:
            True if successful, False otherwise.
        """
        if self._client is None:
            return False

        response = await self._client.post(
            self._logs_url,
            json=entries,
            headers={
                "DD-API-KEY": self._api_key,
                "Content-Type": "application/json",
            },
        )

        if response.is_success:
            datadog_events_total.labels(sink_name=self.name).inc(count)
            return True

        logger.warning(
            "Datadog Logs send failed with status %d",
            response.status_code,
            extra={
                "sink_name": self.name,
                "status_code": response.status_code,
            },
        )
        return False

    async def health_check(self) -> SinkStatus:
        """Check Datadog Logs API connectivity.

        Sends a test event to verify the API key is valid.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        if self._client is None:
            return SinkStatus(healthy=False, reachable=False, last_error="Client not started")

        try:
            test_entry = {
                "ddsource": self._source_tag,
                "ddtags": "env:healthcheck",
                "hostname": "anonreq-healthcheck",
                "service": "anonreq",
                "message": '{"event_type": "health_check", "severity": "informational"}',
            }
            response = await self._client.post(
                self._logs_url,
                json=[test_entry],
                headers={
                    "DD-API-KEY": self._api_key,
                    "Content-Type": "application/json",
                },
            )

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
