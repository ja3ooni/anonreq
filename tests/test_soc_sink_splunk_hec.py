"""Tests for Splunk HEC SIEM sink.

Tests for:
- HEC envelope format correctness
- Authorization header format
- Successful and failed sends
- Batch sends
- Health check
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from anonreq.soc.event import NormalizedEvent, SeverityLevel


def _make_event(
    event_type: str = "test_event",
    mitre_id: str = "T9999",
    severity: SeverityLevel = SeverityLevel.HIGH,
) -> NormalizedEvent:
    return NormalizedEvent(
        severity=severity,
        event_type=event_type,
        tenant_id="tenant-abc",
        session_id="sess-123",
        timestamp="2026-06-26T14:30:00.123456Z",
        gateway_version="1.5.0",
        appliance_instance_id="anonreq-prod-us-east-1a",
        mitre_technique_id=mitre_id,
        metadata={"dlp_category": "pii", "confidence": 0.95},
    )


class TestSplunkHECFormat:
    """Tests for SplunkHECSink.format_event()."""

    @pytest.mark.asyncio
    async def test_format_event_returns_hec_envelope(self):
        """Test 1: format_event produces valid HEC envelope JSON."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint="https://splunk.local:8088/services/collector/event",
            token="test-token-12345",
        )
        await sink.start()

        try:
            event = _make_event()
            envelope = await sink.format_event(event)

            assert "time" in envelope
            assert "host" in envelope
            assert "source" in envelope
            assert "sourcetype" in envelope
            assert "event" in envelope

            assert envelope["host"] == "anonreq-prod-us-east-1a"
            assert envelope["source"] == "anonreq"
            assert envelope["sourcetype"] == "anonreq:ai_security"

            ev = envelope["event"]
            assert ev["severity"] == "high"
            assert ev["event_type"] == "test_event"
            assert ev["tenant_id"] == "tenant-abc"
            assert ev["session_id"] == "sess-123"
            assert ev["mitre_technique_id"] == "T9999"
            assert ev["metadata"]["dlp_category"] == "pii"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_time_field_is_number(self):
        """Time field in HEC envelope is a Unix timestamp (float)."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint="https://splunk.local:8088/services/collector/event",
            token="test-token-12345",
        )
        await sink.start()

        try:
            event = _make_event()
            envelope = await sink.format_event(event)
            assert isinstance(envelope["time"], (int, float))
            assert envelope["time"] > 0
        finally:
            await sink.stop()


class TestSplunkHECAuth:
    """Tests for Splunk HEC auth header."""

    @pytest.mark.asyncio
    async def test_auth_header_format(self):
        """Test 3: Authorization header set to 'Splunk {token}'."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint="https://splunk.local:8088/services/collector/event",
            token="test-token-12345",
        )
        assert sink._auth_header == "Splunk test-token-12345"


class TestSplunkHECSend:
    """Tests for SplunkHECSink.send_event()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_success(self):
        """Test 4: send_event POSTs to correct URL and returns True on 200."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        url = "https://splunk.local:8088/services/collector/event"
        respx.post(url).mock(return_value=Response(200, json={"text": "Success"}))

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint=url,
            token="test-token",
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            # Verify the request
            request = respx.calls.last.request
            assert request.headers["Authorization"] == "Splunk test-token"
            assert request.headers["Content-Type"] == "application/json"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_failure(self):
        """Test 5: send_event returns False on HTTP error."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        url = "https://splunk.local:8088/services/collector/event"
        respx.post(url).mock(return_value=Response(401, text="Unauthorized"))

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint=url,
            token="bad-token",
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
    async def test_send_event_connection_error(self):
        """send_event returns False on connection error."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        url = "https://splunk.local:8088/services/collector/event"
        respx.post(url).mock(side_effect=Exception("Connection refused"))

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint=url,
            token="test-token",
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
    async def test_batch_send(self):
        """Test 7: batch send sends array of events."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        url = "https://splunk.local:8088/services/collector/event"
        respx.post(url).mock(return_value=Response(200, json={"text": "Success"}))

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint=url,
            token="test-token",
        )
        await sink.start()

        try:
            events = [_make_event(event_type=f"test_{i}") for i in range(3)]
            result = await sink.send_batch(events)
            assert result is True
            assert respx.calls.last is not None
        finally:
            await sink.stop()


class TestSplunkHECHealth:
    """Tests for SplunkHECSink.health_check()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_reachable(self):
        """Test 6: health_check returns healthy status."""
        from anonreq.soc.sinks.splunk_hec import SplunkHECSink

        url = "https://splunk.local:8088/services/collector/event"
        respx.get(url.replace("collector/event", "collector/health")).mock(
            return_value=Response(200, text="OK")
        )

        sink = SplunkHECSink(
            name="splunk_test",
            endpoint=url,
            token="test-token",
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is True
        finally:
            await sink.stop()
