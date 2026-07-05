"""Tests for generic webhook SIEM sink.

Tests for:
- Jinja2-subset payload template rendering
- Configurable HTTP method (POST/PUT)
- Configurable Content-Type header
- Configurable auth header
- Configurable timeout
- send_event returns True on 2xx, False otherwise
- Template with unknown fields falls back to empty string
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


class TestWebhookFormat:
    """Tests for WebhookSink.format_event()."""

    @pytest.mark.asyncio
    async def test_default_template_renders_all_fields(self):
        """Default template renders all NormalizedEvent fields."""
        from anonreq.soc.sinks.webhook import WebhookSink

        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
        )
        await sink.start()

        try:
            event = _make_event()
            rendered = await sink.format_event(event)

            # Default template should include all fields
            assert event.event_type in rendered
            assert event.severity.value in rendered
            assert event.tenant_id in rendered
            assert event.session_id in rendered
            assert event.timestamp in rendered
            assert event.gateway_version in rendered
            assert event.appliance_instance_id in rendered
            assert event.mitre_technique_id in rendered
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_custom_template_renders_correctly(self):
        """Test 1: Jinja2-subset payload template renders correctly from NormalizedEvent fields."""
        from anonreq.soc.sinks.webhook import WebhookSink

        template = (
            '{"alert": {"type": "{{ event_type }}", "severity": "{{ severity }}"}, '
            '"tenant": "{{ tenant_id }}"}'
        )
        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            payload_template=template,
        )
        await sink.start()

        try:
            event = _make_event()
            rendered = await sink.format_event(event)

            assert '"type": "dlp_violation"' in rendered
            assert '"severity": "high"' in rendered
            assert '"tenant": "tenant-abc"' in rendered
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_unknown_field_renders_as_empty_string(self):
        """Test 7: Template with unknown field references gracefully falls back to empty string."""
        from anonreq.soc.sinks.webhook import WebhookSink

        template = '{"unknown": "{{ nonexistent_field }}"}'
        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            payload_template=template,
        )
        await sink.start()

        try:
            event = _make_event()
            rendered = await sink.format_event(event)

            # Unknown field should render as empty string
            assert '"unknown": ""' in rendered
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_metadata_tojson_filter(self):
        """Template filter 'tojson' works for metadata dict."""
        from anonreq.soc.sinks.webhook import WebhookSink

        template = '{"meta": {{ metadata | tojson }}}'
        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            payload_template=template,
        )
        await sink.start()

        try:
            event = _make_event()
            rendered = await sink.format_event(event)

            # Should contain the metadata fields serialized as JSON
            assert "dlp_category" in rendered
            assert '"pii"' in rendered
            assert "confidence" in rendered
        finally:
            await sink.stop()


class TestWebhookConfig:
    """Tests for WebhookSink configuration."""

    @pytest.mark.asyncio
    async def test_custom_http_method(self):
        """Test 2: Configurable HTTP method (POST/PUT) applied to request."""
        from anonreq.soc.sinks.webhook import WebhookSink

        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            method="PUT",
        )
        assert sink._method == "PUT"

        sink2 = WebhookSink(
            name="webhook_test2",
            url="https://hooks.example.com/events",
            method="POST",
        )
        assert sink2._method == "POST"

    @pytest.mark.asyncio
    async def test_custom_content_type(self):
        """Test 3: Configurable Content-Type header applied."""
        from anonreq.soc.sinks.webhook import WebhookSink

        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            content_type="application/xml",
        )
        assert sink._content_type == "application/xml"

    @pytest.mark.asyncio
    async def test_custom_headers(self):
        """Test 4: Configurable auth header applied."""
        from anonreq.soc.sinks.webhook import WebhookSink

        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            headers={
                "Authorization": "Bearer test-token-123",
                "X-Custom": "custom-value",
            },
        )
        await sink.start()

        try:
            assert sink._headers["Authorization"] == "Bearer test-token-123"
            assert sink._headers["X-Custom"] == "custom-value"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test 5: Configurable timeout handled."""
        from anonreq.soc.sinks.webhook import WebhookSink

        sink = WebhookSink(
            name="webhook_test",
            url="https://hooks.example.com/events",
            timeout=60,
        )
        assert sink._timeout == 60


class TestWebhookSend:
    """Tests for WebhookSink.send_event()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_post_success(self):
        """Test 6: send_event returns True on 2xx."""
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            request = respx.calls.last.request
            assert request.headers["Content-Type"] == "application/json"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_put_success(self):
        """send_event works with PUT method."""
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.put(url).mock(return_value=Response(200, json={"status": "ok"}))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
            method="PUT",
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            request = respx.calls.last.request
            assert request.method == "PUT"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_failure(self):
        """send_event returns False on non-2xx."""
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.post(url).mock(return_value=Response(500, text="Internal Error"))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
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
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.post(url).mock(side_effect=Exception("Connection refused"))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
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
    async def test_send_event_with_auth_header(self):
        """send_event includes custom auth headers."""
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
            headers={
                "Authorization": "Bearer custom-token",
                "X-API-Key": "secret-key",
            },
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            request = respx.calls.last.request
            assert request.headers["Authorization"] == "Bearer custom-token"
            assert request.headers["X-API-Key"] == "secret-key"
        finally:
            await sink.stop()


class TestWebhookHealth:
    """Tests for WebhookSink.health_check()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_reachable(self):
        """health_check returns healthy when endpoint is reachable."""
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.options(url).mock(return_value=Response(200, text="OK"))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
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
        from anonreq.soc.sinks.webhook import WebhookSink

        url = "https://hooks.example.com/events"
        respx.options(url).mock(return_value=Response(503, text="Unavailable"))

        sink = WebhookSink(
            name="webhook_test",
            url=url,
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is False
            assert status.reachable is False
        finally:
            await sink.stop()
