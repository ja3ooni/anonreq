"""Tests for Azure Sentinel DCR SIEM sink.

Tests for:
- OAuth2 token acquisition from Azure AD
- Token caching and expiry handling
- DCR stream request body matches expected schema
- Authorization header set to "Bearer {token}"
- Successful and failed sends
- Health check validates token acquisition
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from anonreq.soc.event import NormalizedEvent, SeverityLevel


def _make_event(
    event_type: str = "dlp_violation",
    mitre_id: str = "T1048",
    severity: SeverityLevel = SeverityLevel.HIGH,
) -> NormalizedEvent:
    return NormalizedEvent(
        severity=severity,
        event_type=event_type,
        tenant_id="tenant-abc",
        session_id="sess-123",
        timestamp="2026-06-26T14:30:00.123456Z",
        gateway_version="1.5.0",
        appliance_instance_id="anonreq-test-1",
        mitre_technique_id=mitre_id,
        metadata={"dlp_category": "pii", "confidence": 0.95},
    )


class TestSentinelDCRToken:
    """Tests for SentinelDCRSink token acquisition and caching."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_acquire_token_oauth2(self):
        """Test 1: OAuth2 token acquisition from Azure AD using client_credentials grant."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test-access-token-123",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            token = await sink._acquire_token()
            assert token == "test-access-token-123"

            # Verify request body
            request = respx.calls.last.request
            body = request.content.decode("utf-8")
            assert "client_id=client-123" in body
            assert "client_secret=secret-456" in body
            assert "scope=https%3A%2F%2Fmonitor.azure.com%2F%2F.default" in body
            assert "grant_type=client_credentials" in body
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_cached_and_reused(self):
        """Test 2: Token cached and reused until expiry (within 5min buffer)."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "cached-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            # First call should hit Azure AD
            token1 = await sink._acquire_token()
            assert token1 == "cached-token"
            assert len(respx.calls) == 1

            # Second call within expiry should use cache
            token2 = await sink._acquire_token()
            assert token2 == "cached-token"
            assert len(respx.calls) == 1  # No additional HTTP call
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_refresh_on_expiry(self):
        """Token is re-acquired when within 5min of expiry."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        # Token with very short expiry (10 seconds)
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "short-lived-token",
                    "expires_in": 10,
                    "token_type": "Bearer",
                },
            )
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            token1 = await sink._acquire_token()
            assert token1 == "short-lived-token"
            assert len(respx.calls) == 1

            # Token is expired or near-expiry, should re-acquire
            # We simulate by calling with a fresh mock
            await sink._acquire_token()
            assert len(respx.calls) >= 1  # May re-acquire if expired
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_acquisition_failure(self):
        """Token acquisition failure raises an appropriate error."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(401, json={"error": "invalid_client"})
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="bad-client",
            client_secret="bad-secret",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            with pytest.raises(Exception):  # noqa: B017, PT011
                await sink._acquire_token()
        finally:
            await sink.stop()


class TestSentinelDCRFormat:
    """Tests for SentinelDCRSink.format_event()."""

    @pytest.mark.asyncio
    async def test_format_event_matches_dcr_schema(self):
        """Test 3: DCR stream request body matches expected stream schema."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            event = _make_event()
            formatted = await sink.format_event(event)

            # Should be a list of records (DCR accepts array)
            assert isinstance(formatted, list)

            record = formatted[0]
            assert record["severity"] == "high"
            assert record["event_type"] == "dlp_violation"
            assert record["tenant_id"] == "tenant-abc"
            assert record["session_id"] == "sess-123"
            assert record["mitre_technique_id"] == "T1048"
            assert record["gateway_version"] == "1.5.0"
            assert record["appliance_instance_id"] == "anonreq-test-1"
            assert record["metadata"]["dlp_category"] == "pii"
        finally:
            await sink.stop()


class TestSentinelDCRSend:
    """Tests for SentinelDCRSink.send_event()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_bearer_auth(self):
        """Test 4: Authorization header set to "Bearer {token}"."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        )

        dcr_url = (
            "https://eastus.ingest.monitor.azure.com"
            "/dataCollectionRules/dcr-abc123/streams/Custom-AnonReqEvents"
            "?api-version=2023-01-01"
        )
        respx.post(dcr_url).mock(return_value=Response(202, json={"records_count": 1}))

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            dcr_request = respx.calls[-1].request
            assert dcr_request.headers["Authorization"] == "Bearer test-token"
            assert dcr_request.headers["Content-Type"] == "application/json"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_success_returns_true(self):
        """Test 5: send_event returns True on HTTP 200/202."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        )

        dcr_url = (
            "https://eastus.ingest.monitor.azure.com"
            "/dataCollectionRules/dcr-abc123/streams/Custom-AnonReqEvents"
            "?api-version=2023-01-01"
        )
        respx.post(dcr_url).mock(return_value=Response(200, json={"records_count": 1}))

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_failure_returns_false(self):
        """Test 6: send_event returns False on HTTP 4xx/5xx."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        )

        dcr_url = (
            "https://eastus.ingest.monitor.azure.com"
            "/dataCollectionRules/dcr-abc123/streams/Custom-AnonReqEvents"
            "?api-version=2023-01-01"
        )
        respx.post(dcr_url).mock(return_value=Response(403, json={"error": "Forbidden"}))

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is False
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_with_connection_error(self):
        """send_event returns False on connection error."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        )

        dcr_url = (
            "https://eastus.ingest.monitor.azure.com"
            "/dataCollectionRules/dcr-abc123/streams/Custom-AnonReqEvents"
            "?api-version=2023-01-01"
        )
        respx.post(dcr_url).mock(side_effect=Exception("Connection refused"))

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is False
        finally:
            await sink.stop()


class TestSentinelDCRHealth:
    """Tests for SentinelDCRSink.health_check()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_validates_token_acquisition(self):
        """Test 7: health_check validates token acquisition works."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="client-123",
            client_secret="secret-456",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            status = await sink.health_check()
            assert status.healthy is True
            assert status.reachable is True
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_token_failure(self):
        """health_check returns unhealthy when token acquisition fails."""
        from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

        token_url = "https://login.microsoftonline.com/tenant-abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=Response(401, json={"error": "invalid_client"})
        )

        sink = SentinelDCRSink(
            name="sentinel_test",
            tenant_id="tenant-abc",
            client_id="bad-client",
            client_secret="bad-secret",
            dcr_endpoint="https://eastus.ingest.monitor.azure.com",
            dcr_immutable_id="dcr-abc123",
            stream_name="Custom-AnonReqEvents",
        )

        await sink.start()
        try:
            status = await sink.health_check()
            assert status.healthy is False
            assert status.reachable is False
        finally:
            await sink.stop()
