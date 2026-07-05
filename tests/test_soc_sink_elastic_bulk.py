"""Tests for Elastic Security Bulk API SIEM sink.

Tests for:
- NDJSON formatting: action_meta + event lines
- Index name date substitution
- API key auth header format
- Successful and failed sends
- Batch send
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


class TestElasticBulkFormat:
    """Tests for ElasticBulkSink.format_event()."""

    @pytest.mark.asyncio
    async def test_format_event_returns_ndjson(self):
        """Test 1: NDJSON format: action_meta line + event line per event."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="base64apikey123",
        )
        await sink.start()

        try:
            event = _make_event()
            ndjson = await sink.format_event(event)
            lines = ndjson.strip().split("\n")

            assert len(lines) == 2

            # First line: action_meta
            action_meta = json.loads(lines[0])
            assert "create" in action_meta
            assert "_index" in action_meta["create"]
            assert "_id" in action_meta["create"]
            assert "tenant-abc_sess-123_dlp_violation" == action_meta["create"]["_id"]

            # Second line: event body
            event_body = json.loads(lines[1])
            assert event_body["severity"] == "high"
            assert event_body["event_type"] == "dlp_violation"
            assert event_body["tenant_id"] == "tenant-abc"
            assert event_body["session_id"] == "sess-123"
            assert event_body["mitre_technique_id"] == "T1048"
            assert event_body["gateway_version"] == "1.5.0"
            assert event_body["metadata"]["dlp_category"] == "pii"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_index_pattern_with_date_substitution(self):
        """Test 2: Action meta line has correct index name with date substitution."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="base64apikey123",
            index_pattern="custom-index-%Y.%m.%d",
        )
        await sink.start()

        try:
            event = _make_event()
            ndjson = await sink.format_event(event)
            action_meta = json.loads(ndjson.strip().split("\n")[0])

            # Index name should contain the date pattern substituted
            index_name = action_meta["create"]["_index"]
            assert index_name.startswith("custom-index-")
            # Should have the date in the format YYYY.MM.DD
            parts = index_name.split("-")
            date_part = parts[-1]
            assert len(date_part) == 10  # YYYY.MM.DD = 10 chars
            assert "." in date_part
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_default_index_pattern(self):
        """Test 3: Default index pattern: 'anonreq-ai-security-%Y.%m.%d' resolves correctly."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink, DEFAULT_INDEX_PATTERN

        assert DEFAULT_INDEX_PATTERN == "anonreq-ai-security-%Y.%m.%d"

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="base64apikey123",
        )
        await sink.start()

        try:
            event = _make_event()
            ndjson = await sink.format_event(event)
            action_meta = json.loads(ndjson.strip().split("\n")[0])
            index_name = action_meta["create"]["_index"]
            assert index_name.startswith("anonreq-ai-security-")
            date_part = index_name.split("-")[-1]
            assert "." in date_part
            assert len(date_part) == 10
        finally:
            await sink.stop()


class TestElasticBulkAuth:
    """Tests for ElasticBulkSink auth header."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_auth_header(self):
        """Test 4: API key auth header: 'ApiKey {base64_encoded_key}'."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(return_value=Response(200, json={"errors": False, "items": []}))

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            request = respx.calls.last.request
            assert request.headers["Authorization"] == "ApiKey dGVzdC1hcGkta2V5"
            assert request.headers["Content-Type"] == "application/x-ndjson"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_api_key_not_base64_raises_value_error(self):
        """API key that is not valid base64 is encoded if needed."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        # A raw key (not base64-encoded) should work too
        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="raw-api-key",
        )

        # Should encode as base64
        assert sink._auth_header_value == "ApiKey cmF3LWFwaS1rZXk="


class TestElasticBulkSend:
    """Tests for ElasticBulkSink.send_event()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_success(self):
        """Test 5: send_event returns True on HTTP 200/201 with no errors."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(
            return_value=Response(200, json={"errors": False, "items": [{"create": {"status": 201}}]})
        )

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
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
    async def test_bulk_response_with_errors_returns_false(self):
        """Test 6: Bulk response with errors returns False."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(
            return_value=Response(
                200,
                json={
                    "errors": True,
                    "items": [{"create": {"status": 400, "error": {"reason": "Invalid field"}}}],
                },
            )
        )

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
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
    async def test_send_event_http_error(self):
        """send_event returns False on HTTP 4xx/5xx."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(return_value=Response(401, text="Unauthorized"))

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
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
    async def test_send_batch(self):
        """Batch send sends NDJSON with multiple event pairs."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(
            return_value=Response(200, json={"errors": False, "items": []})
        )

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
        )
        await sink.start()

        try:
            events = [_make_event(event_type=f"test_{i}") for i in range(3)]
            result = await sink.send_batch(events)
            assert result is True

            # Verify NDJSON has 6 lines (2 per event × 3 events)
            request_body = respx.calls.last.request.content.decode("utf-8")
            lines = request_body.strip().split("\n")
            assert len(lines) == 6
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_event_connection_error(self):
        """send_event returns False on connection error."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/_bulk"
        respx.post(url).mock(side_effect=Exception("Connection refused"))

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is False
        finally:
            await sink.stop()


class TestElasticBulkHealth:
    """Tests for ElasticBulkSink.health_check()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_connectivity(self):
        """Test 7: health_check tests connectivity to Elastic endpoint."""
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/"
        respx.get(url).mock(
            return_value=Response(200, json={"version": {"number": "8.12.0"}})
        )

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
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
        from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

        url = "https://elastic.local:9200/"
        respx.get(url).mock(return_value=Response(503, text="Unavailable"))

        sink = ElasticBulkSink(
            name="elastic_test",
            endpoint="https://elastic.local:9200",
            api_key="dGVzdC1hcGkta2V5",
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is False
            assert status.reachable is False
        finally:
            await sink.stop()
