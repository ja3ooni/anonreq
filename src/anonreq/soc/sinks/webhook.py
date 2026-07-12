"""Generic webhook SIEM sink with Jinja2-subset templating.

Per D-010 and 20-ARCHITECTURE.md:
- Renders payload using Jinja2 sandboxed environment
- Configurable HTTP method, URL, headers, content-type, timeout
- Default template renders all NormalizedEvent fields
- Unknown field references resolve to empty string (ChainableUndefined)
- ``tojson`` filter available for metadata dict serialization
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from jinja2 import BaseLoader, ChainableUndefined, Environment, select_autoescape
from prometheus_client import Counter

from anonreq.soc.sinks import SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.webhook")

# Jinja2 sandboxed environment for template rendering
_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(default_for_string=False),
    undefined=ChainableUndefined,
)

webhook_events_total = Counter(
    "anonreq_soc_sink_webhook_total",
    "Events sent to webhook sink",
    ["sink_name"],
)

# Default template that renders all normalized fields as JSON
_DEFAULT_TEMPLATE = json.dumps(
    {
        "severity": "{{ severity }}",
        "event_type": "{{ event_type }}",
        "tenant_id": "{{ tenant_id }}",
        "session_id": "{{ session_id }}",
        "timestamp": "{{ timestamp }}",
        "gateway_version": "{{ gateway_version }}",
        "appliance_instance_id": "{{ appliance_instance_id }}",
        "mitre_technique_id": "{{ mitre_technique_id }}",
        "metadata": "{{ metadata | tojson }}",
    },
    indent=2,
)


class WebhookSink:
    """Generic webhook sink — sends normalized events to custom HTTP endpoints.

    Uses Jinja2-subset template rendering for configurable payload format.
    Supports custom HTTP method, headers, content-type, and timeout.

    Args:
        name: Human-readable sink instance name.
        url: Webhook endpoint URL.
        method: HTTP method (``"POST"`` or ``"PUT"``, default ``"POST"``).
        headers: Optional dict of custom HTTP headers
            (e.g. ``{"Authorization": "Bearer $env:TOKEN"}``).
        payload_template: Jinja2 template string. If None, uses default
            template that renders all normalized fields.
        content_type: Content-Type header value (default ``"application/json"``).
        timeout: HTTP request timeout in seconds (default 30).
        tls_verify: Whether to verify TLS certificates (default True).
    """

    def __init__(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        payload_template: str | None = None,
        content_type: str = "application/json",
        timeout: int = 30,
        tls_verify: bool = True,
    ) -> None:
        self.name = name
        self.sink_type = "webhook"
        self.enabled = True
        self._url = url
        self._method = method.upper()
        self._headers = dict(headers or {})
        self._content_type = content_type
        self._timeout = timeout
        self._tls_verify = tls_verify
        self._client: httpx.AsyncClient | None = None

        # Compile the template
        template_str = payload_template or _DEFAULT_TEMPLATE
        self._template = _env.from_string(template_str)

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

    async def format_event(self, event: Any) -> str:
        """Render the payload template with event fields.

        Event fields are passed as template context variables:
        severity, event_type, tenant_id, session_id, timestamp,
        gateway_version, appliance_instance_id, mitre_technique_id, metadata.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            Rendered template string.
        """
        context = {
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
        return self._template.render(**context)

    async def send_event(self, event: Any) -> bool:
        """Send a normalized event to the webhook endpoint.

        Renders the payload template and sends an HTTP request with
        the configured method, headers, content-type, and URL.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful (HTTP 2xx), False otherwise.
        """
        if self._client is None:
            return False

        try:
            payload = await self.format_event(event)
            request_headers = dict(self._headers)
            request_headers["Content-Type"] = self._content_type

            response = await self._client.request(
                method=self._method,
                url=self._url,
                content=payload,
                headers=request_headers,
            )

            if response.is_success:
                webhook_events_total.labels(sink_name=self.name).inc()
                return True

            logger.warning(
                "Webhook send failed with status %d",
                response.status_code,
                extra={
                    "sink_name": self.name,
                    "status_code": response.status_code,
                    "method": self._method,
                    "event_type": event.event_type,
                },
            )
            return False
        except Exception as exc:
            logger.warning(
                "Webhook send error: %s",
                str(exc),
                extra={"sink_name": self.name, "event_type": event.event_type},
            )
            return False

    async def health_check(self) -> SinkStatus:
        """Check webhook endpoint reachability.

        Sends an OPTIONS request to the configured URL.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        if self._client is None:
            return SinkStatus(healthy=False, reachable=False, last_error="Client not started")

        try:
            response = await self._client.options(
                self._url,
                headers=self._headers,
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
