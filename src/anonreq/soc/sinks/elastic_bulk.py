"""Elasticsearch Bulk API SIEM sink.

Per D-008 and 20-ARCHITECTURE.md:
- Formats normalized events as NDJSON (action_meta + event_body per event)
- POSTs to ``{endpoint}/_bulk`` with ``Content-Type: application/x-ndjson``
- Authorization: ``ApiKey {base64_encoded_key}``
- Configurable index pattern with date substitution (default: ``anonreq-ai-security-%Y.%m.%d``)
- Supports batch sends
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from prometheus_client import Counter

from anonreq.soc.sinks import SinkBase, SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.elastic_bulk")

DEFAULT_INDEX_PATTERN = "anonreq-ai-security-%Y.%m.%d"

elastic_events_total = Counter(
    "anonreq_soc_sink_elastic_bulk_total",
    "Events sent to Elasticsearch Bulk sink",
    ["sink_name"],
)


class ElasticBulkSink:
    """Elasticsearch Bulk API sink — sends events as NDJSON via Bulk API.

    Formats normalized events as NDJSON action_meta + event_body pairs
    and POSTs them to the Elasticsearch ``_bulk`` endpoint.

    Args:
        name: Human-readable sink instance name.
        endpoint: Elasticsearch endpoint URL with port
            (e.g. ``https://elastic-instance:9200``).
        api_key: Base64-encoded API key or raw key (auto-encodes if not base64).
        index_pattern: Index name pattern with ``strftime`` codes
            (default ``anonreq-ai-security-%Y.%m.%d``).
        tls_verify: Whether to verify TLS certificates (default True).
        timeout: HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        index_pattern: str = DEFAULT_INDEX_PATTERN,
        tls_verify: bool = True,
        timeout: int = 30,
    ) -> None:
        self.name = name
        self.sink_type = "elastic_bulk"
        self.enabled = True
        self._endpoint = endpoint.rstrip("/")
        self._index_pattern = index_pattern
        self._tls_verify = tls_verify
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

        # Auto-encode API key if not already base64
        self._auth_header_value = self._build_auth_header(api_key)

    @staticmethod
    def _build_auth_header(api_key: str) -> str:
        """Build the Authorization header value.

        If the key is already valid base64, use as-is.
        Otherwise, encode as base64.

        Args:
            api_key: Raw or base64-encoded API key.

        Returns:
            ``ApiKey {encoded_key}`` string.
        """
        # Check if already base64
        try:
            base64.b64decode(api_key, validate=True)
            encoded = api_key
        except Exception:
            encoded = base64.b64encode(api_key.encode()).decode()
        return f"ApiKey {encoded}"

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

    async def _format_index(self) -> str:
        """Apply datetime strftime substitution to the index pattern.

        Returns:
            Index name with date placeholders resolved.
        """
        now = datetime.now(timezone.utc)
        return now.strftime(self._index_pattern)

    async def format_event(self, event: Any) -> str:
        """Format a NormalizedEvent into NDJSON (action_meta + event body).

        Produces two NDJSON lines per event:
        1. Action metadata: ``{"create": {"_index": "...", "_id": "..."}}``
        2. Event body with all normalized fields

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            NDJSON string with action_meta line + event body line.
        """
        index_name = await self._format_index()
        doc_id = f"{event.tenant_id}_{event.session_id}_{event.event_type}"

        action_meta = {"create": {"_index": index_name, "_id": doc_id}}
        event_body = {
            "severity": event.severity.value,
            "event_type": event.event_type,
            "tenant_id": event.tenant_id,
            "session_id": event.session_id,
            "timestamp": event.timestamp,
            "gateway_version": event.gateway_version,
            "appliance_instance_id": event.appliance_instance_id,
            "mitre_technique_id": event.mitre_technique_id,
            "metadata": event.metadata,
        }

        return json.dumps(action_meta) + "\n" + json.dumps(event_body) + "\n"

    async def send_event(self, event: Any) -> bool:
        """Send a single event to Elasticsearch via Bulk API.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful (HTTP 2xx and no errors),
            False otherwise.
        """
        if self._client is None:
            return False

        try:
            ndjson_body = await self.format_event(event)
            return await self._post_bulk(ndjson_body, 1)
        except Exception as exc:
            logger.warning(
                "Elastic Bulk send error: %s",
                str(exc),
                extra={"sink_name": self.name, "event_type": event.event_type},
            )
            return False

    async def send_batch(self, events: list[Any]) -> bool:
        """Send multiple events in a single Bulk API request.

        Args:
            events: List of ``NormalizedEvent`` instances.

        Returns:
            True if delivery was successful, False otherwise.
        """
        if self._client is None or not events:
            return False

        try:
            lines = [await self.format_event(ev) for ev in events]
            ndjson_body = "".join(lines)
            return await self._post_bulk(ndjson_body, len(events))
        except Exception as exc:
            logger.warning(
                "Elastic Bulk batch send error: %s",
                str(exc),
                extra={"sink_name": self.name},
            )
            return False

    async def _post_bulk(self, ndjson_body: str, count: int) -> bool:
        """POST NDJSON body to the _bulk endpoint.

        Args:
            ndjson_body: NDJSON-formatted request body.
            count: Number of events for metric counting.

        Returns:
            True if successful, False otherwise.
        """
        if self._client is None:
            return False

        response = await self._client.post(
            f"{self._endpoint}/_bulk",
            content=ndjson_body,
            headers={
                "Authorization": self._auth_header_value,
                "Content-Type": "application/x-ndjson",
            },
        )

        if response.is_success:
            result = response.json()
            if result.get("errors"):
                logger.warning(
                    "Elastic Bulk response contained errors",
                    extra={"sink_name": self.name},
                )
                return False
            elastic_events_total.labels(sink_name=self.name).inc(count)
            return True

        logger.warning(
            "Elastic Bulk send failed with status %d",
            response.status_code,
            extra={"sink_name": self.name, "status_code": response.status_code},
        )
        return False

    async def health_check(self) -> SinkStatus:
        """Check Elasticsearch endpoint connectivity.

        Sends a GET request to the root endpoint to verify connectivity.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        if self._client is None:
            return SinkStatus(healthy=False, reachable=False, last_error="Client not started")

        try:
            response = await self._client.get(
                f"{self._endpoint}/",
                headers={"Authorization": self._auth_header_value},
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
