"""Tests for Datadog Logs API SIEM sink.

Tests for:
- JSON array format correct
- DD-API-KEY header set correctly in request headers
- Configurable log source tag (default: "anonreq")
- Successful and failed sends
- Batch send sends array of events
- Health check
"""

from __future__ import annotations

import json

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


class TestDatadogLogsFormat:
    """Tests for DatadogLogsSink.format_event()."""

    @pytest.mark.asyncio
    async def test_format_event_returns_dd_log_entry(self):
        """Test 1: JSON array format correct."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
        )
        await sink.start()

        try:
            event = _make_event()
            formatted = await sink.format_event(event)

            assert formatted["ddsource"] == "anonreq"
            assert "ddtags" in formatted
            assert "env:production" in formatted["ddtags"]
            assert "tenant:tenant-abc" in formatted["ddtags"]
            assert formatted["hostname"] == "anonreq-test-1"
            assert formatted["service"] == "anonreq"

            # message should be a JSON string
            message = json.loads(formatted["message"])
            assert message["severity"] == "high"
            assert message["event_type"] == "dlp_violation"
            assert message["session_id"] == "sess-123"
            assert message["mitre_technique_id"] == "T1048"
            assert message["metadata"]["dlp_category"] == "pii"
        finally:
            await sink.stop()


class TestDatadogLogsAuth:
    """Tests for DatadogLogsSink auth header."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_dd_api_key_header(self):
        """Test 2: DD-API-KEY header set correctly in request headers."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(202, json={"status": "ok"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            request = respx.calls.last.request
            assert request.headers["DD-API-KEY"] == "test-api-key-12345"
            assert request.headers["Content-Type"] == "application/json"
        finally:
            await sink.stop()


class TestDatadogLogsConfig:
    """Tests for DatadogLogsSink configuration."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_source_tag(self):
        """Test 3: Configurable log source tag (default: 'anonreq') in each event."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(202, json={"status": "ok"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
            source_tag="custom-security",
        )
        await sink.start()

        try:
            event = _make_event()
            formatted = await sink.format_event(event)
            assert formatted["ddsource"] == "custom-security"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_custom_site(self):
        """Configurable Datadog site."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
            site="datadoghq.eu",
        )
        await sink.start()

        try:
            assert "datadoghq.eu" in sink._logs_url
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_default_source_tag(self):
        """Default source tag is 'anonreq'."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink, DEFAULT_SOURCE_TAG

        assert DEFAULT_SOURCE_TAG == "anonreq"


class TestDatadogLogsSend:
    """Tests for DatadogLogsSink.send_event()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_success(self):
        """Test 4: send_event returns True on HTTP 202."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(202, json={"status": "ok"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
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
    async def test_send_event_failure(self):
        """Test 5: send_event returns False on HTTP 4xx/5xx."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(403, json={"error": "invalid_api_key"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="bad-key",
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
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(side_effect=Exception("Connection timeout"))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
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
    async def test_send_batch(self):
        """Test 6: Batch send sends array of events."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(202, json={"status": "ok"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
        )
        await sink.start()

        try:
            events = [_make_event(event_type=f"test_{i}") for i in range(3)]
            result = await sink.send_batch(events)
            assert result is True

            # Verify array of 3 events was sent
            request_body = json.loads(respx.calls.last.request.content)
            assert isinstance(request_body, list)
            assert len(request_body) == 3
        finally:
            await sink.stop()


class TestDatadogLogsHealth:
    """Tests for DatadogLogsSink.health_check()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_reachable(self):
        """Test 7: health_check POSTs test event to verify connectivity."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(202, json={"status": "ok"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="test-api-key-12345",
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
    async def test_health_check_unreachable(self):
        """health_check returns unhealthy when endpoint is unreachable."""
        from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

        url = "https://http-intake.logs.datadoghq.com/api/v2/logs"
        respx.post(url).mock(return_value=Response(401, json={"error": "invalid_api_key"}))

        sink = DatadogLogsSink(
            name="dd_test",
            api_key="bad-key",
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is False
            assert status.reachable is False
        finally:
            await sink.stop()
