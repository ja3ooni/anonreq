"""Azure Sentinel DCR (Data Collection Rules) SIEM sink.

Per D-007 and 20-ARCHITECTURE.md:
- Authenticates via OAuth2 client_credentials grant to Azure AD
- Formats normalized events as DCR stream records
- POSTs to ``{dcr_endpoint}/dataCollectionRules/{id}/streams/{name}?api-version=2023-01-01``
- Authorization header: ``Bearer {access_token}``
- Token cached in memory with 5min refresh buffer
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from prometheus_client import Counter

from anonreq.soc.sinks import SinkStatus

logger = logging.getLogger("anonreq.soc.sinks.sentinel_dcr")

# Azure AD OAuth2 constants
OAUTH2_SCOPE = "https://monitor.azure.com//.default"
TOKEN_GRANT_TYPE = "client_credentials"

sentinel_events_total = Counter(
    "anonreq_soc_sink_sentinel_dcr_total",
    "Events sent to Azure Sentinel DCR sink",
    ["sink_name"],
)


class SentinelDCRSink:
    """Azure Sentinel DCR sink — sends normalized events via DCR API.

    Authenticates via OAuth2 client_credentials grant to Azure AD,
    acquires a Bearer token, and POSTs events to the DCR stream endpoint.

    Args:
        name: Human-readable sink instance name.
        tenant_id: Azure AD tenant ID.
        client_id: Azure AD application (client) ID.
        client_secret: Azure AD client secret.
        dcr_endpoint: DCR ingestion endpoint
            (e.g. ``https://eastus.ingest.monitor.azure.com``).
        dcr_immutable_id: DCR immutable ID from Azure.
        stream_name: Custom table stream name.
        tls_verify: Whether to verify TLS certificates (default True).
        timeout: HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        name: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        dcr_endpoint: str,
        dcr_immutable_id: str,
        stream_name: str,
        tls_verify: bool = True,
        timeout: int = 30,
    ) -> None:
        self.name = name
        self.sink_type = "sentinel_dcr"
        self.enabled = True
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._dcr_endpoint = dcr_endpoint.rstrip("/")
        self._dcr_immutable_id = dcr_immutable_id
        self._stream_name = stream_name
        self._tls_verify = tls_verify
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

        # Token cache
        self._cached_token: str | None = None
        self._token_expiry: float = 0.0
        self._token_buffer: int = 300  # 5 minutes buffer before expiry

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

    async def _acquire_token(self) -> str:
        """Acquire an OAuth2 access token via client_credentials grant.

        Returns cached token if still valid (within 5min buffer of expiry).
        Otherwise acquires a new token from Azure AD.

        Returns:
            Bearer access token string.

        Raises:
            RuntimeError: If token acquisition fails.
        """
        # Check cache with 5min buffer
        now = time.time()
        if self._cached_token is not None and now < (self._token_expiry - self._token_buffer):
            return self._cached_token

        if self._client is None:
            raise RuntimeError("Sink not started")

        token_url = (
            f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        )
        body = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": OAUTH2_SCOPE,
            "grant_type": TOKEN_GRANT_TYPE,
        }

        response = await self._client.post(
            token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if not response.is_success:
            raise RuntimeError(
                f"Token acquisition failed: HTTP {response.status_code}"
            )

        data = response.json()
        self._cached_token = data["access_token"]
        self._token_expiry = now + float(data.get("expires_in", 3600))
        return self._cached_token

    async def _get_dcr_url(self) -> str:
        """Build the DCR stream ingestion URL.

        Returns:
            Full DCR endpoint URL with query parameters.
        """
        return (
            f"{self._dcr_endpoint}/dataCollectionRules/{self._dcr_immutable_id}"
            f"/streams/{self._stream_name}?api-version=2023-01-01"
        )

    async def format_event(self, event: Any) -> list[dict[str, Any]]:
        """Format a NormalizedEvent into a DCR stream record list.

        Azure DCR accepts an array of records matching the custom table schema.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            List of DCR stream record dicts (single-element list).
        """
        return [
            {
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
        ]

    async def send_event(self, event: Any) -> bool:
        """Send a single event to Azure Sentinel via DCR.

        Acquires an OAuth2 token and POSTs the formatted event to the
        DCR stream endpoint with Bearer auth.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful (HTTP 200/202), False otherwise.
        """
        if self._client is None:
            return False

        try:
            token = await self._acquire_token()
            records = await self.format_event(event)
            dcr_url = await self._get_dcr_url()

            response = await self._client.post(
                dcr_url,
                json=records,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if response.is_success:
                sentinel_events_total.labels(sink_name=self.name).inc()
                return True

            logger.warning(
                "Sentinel DCR send failed with status %d",
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
                "Sentinel DCR send error: %s",
                str(exc),
                extra={"sink_name": self.name, "event_type": event.event_type},
            )
            return False

    async def health_check(self) -> SinkStatus:
        """Check Sentinel DCR connectivity by testing token acquisition.

        Attempts to acquire an OAuth2 token. If successful, returns healthy.
        If token acquisition fails, returns unhealthy with error details.

        Returns:
            ``SinkStatus`` indicating reachability and health.
        """
        if self._client is None:
            return SinkStatus(healthy=False, reachable=False, last_error="Client not started")

        try:
            await self._acquire_token()
            return SinkStatus(healthy=True, reachable=True)
        except Exception as exc:
            return SinkStatus(
                healthy=False,
                reachable=False,
                last_error=str(exc),
            )
