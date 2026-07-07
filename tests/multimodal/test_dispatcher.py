from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from anonreq.multimodal.models import AnalyzerResult, ContentType, UnifiedDetectionResult


@pytest.fixture
def mock_json_analyzer():
    m = AsyncMock()
    m.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.APPLICATION_JSON,
        entities=[{"entity_type": "PERSON", "start": 0, "end": 5, "score": 0.95}],
        risk_score=0.5,
        classification="Sensitive",
    )
    return m


@pytest.fixture
def mock_multipart_analyzer():
    m = AsyncMock()
    m.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.MULTIPART_FORM_DATA,
        entities=[],
        risk_score=0.0,
        classification="Internal",
    )
    return m


@pytest.fixture
def mock_text_analyzer():
    m = AsyncMock()
    m.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.TEXT_PLAIN,
        entities=[],
        risk_score=0.0,
        classification="Internal",
    )
    return m


class TestContentTypeEnum:
    def test_text_plain_value(self):
        assert ContentType.TEXT_PLAIN.value == "text/plain"

    def test_application_json_value(self):
        assert ContentType.APPLICATION_JSON.value == "application/json"

    def test_multipart_form_data_value(self):
        assert ContentType.MULTIPART_FORM_DATA.value == "multipart/form-data"

    def test_unknown_value(self):
        assert ContentType.UNKNOWN.value == "unknown"

    def test_agent_content_type_values(self):
        assert ContentType.AGENT_TOOL_CALL.value == "agent_tool_call"
        assert ContentType.AGENT_TOOL_RESULT.value == "agent_tool_result"
        assert ContentType.MCP_MESSAGE.value == "mcp_message"


class TestUnifiedDetectionResult:
    def test_default_values(self):
        r = UnifiedDetectionResult(content_type=ContentType.TEXT_PLAIN)
        assert r.entities == []
        assert r.risk_score == 0.0
        assert r.classification == "Internal"
        assert r.analyzer_metadata == {}

    def test_with_entities(self):
        r = UnifiedDetectionResult(
            content_type=ContentType.APPLICATION_JSON,
            entities=[{"entity_type": "EMAIL", "value": "test@example.com"}],
            risk_score=0.8,
            classification="Critical",
        )
        assert len(r.entities) == 1
        assert r.entities[0]["entity_type"] == "EMAIL"


class TestAnalyzerResult:
    def test_default_values(self):
        dr = UnifiedDetectionResult(content_type=ContentType.TEXT_PLAIN)
        r = AnalyzerResult(
            source_analyzer="test",
            content_type=ContentType.TEXT_PLAIN,
            detection_result=dr,
        )
        assert r.should_process is True
        assert r.action == "ANONYMIZE"

    def test_rouge_local_action(self):
        dr = UnifiedDetectionResult(content_type=ContentType.UNKNOWN)
        r = AnalyzerResult(
            source_analyzer="dispatcher",
            content_type=ContentType.UNKNOWN,
            detection_result=dr,
            action="ROUTE_LOCAL",
            should_process=False,
        )
        assert r.action == "ROUTE_LOCAL"
        assert r.should_process is False


class TestContentTypeDispatcher:
    @pytest.mark.asyncio
    async def test_routes_text_plain(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("text/plain", b"hello", None)
        assert result.content_type == ContentType.TEXT_PLAIN
        assert result.action == "ANONYMIZE"

    @pytest.mark.asyncio
    async def test_routes_application_json(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("application/json", b'{"key": "val"}', None)
        assert result.content_type == ContentType.APPLICATION_JSON
        mock_json_analyzer.analyze.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "header,expected",
        [
            ("application/x-anonreq-agent-tool-call", ContentType.AGENT_TOOL_CALL),
            ("application/x-anonreq-agent-tool-result", ContentType.AGENT_TOOL_RESULT),
            ("application/x-anonreq-mcp", ContentType.MCP_MESSAGE),
            ("application/vnd.mcp+json", ContentType.MCP_MESSAGE),
        ],
    )
    async def test_routes_agent_content_types(
        self,
        header,
        expected,
        mock_json_analyzer,
        mock_multipart_analyzer,
    ):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch(header, b'{"id":"call_1"}', None)
        assert result.content_type == expected
        assert result.action == "ANONYMIZE"
        assert result.detection_result.analyzer_metadata["raw_type"] == header

    @pytest.mark.asyncio
    async def test_routes_multipart_form_data(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("multipart/form-data", b"---data---", None)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA
        mock_multipart_analyzer.analyze.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_type_returns_route_local(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("application/xml", b"<xml/>", None)
        assert result.content_type == ContentType.UNKNOWN
        assert result.action == "ROUTE_LOCAL"
        assert result.should_process is False

    @pytest.mark.asyncio
    async def test_missing_header_defaults_to_text_plain(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("", b"hello", None)
        assert result.content_type == ContentType.TEXT_PLAIN

    @pytest.mark.asyncio
    async def test_strips_charset(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch("text/plain; charset=utf-8", b"hello", None)
        assert result.content_type == ContentType.TEXT_PLAIN

    @pytest.mark.asyncio
    async def test_strips_charset_json(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        result = await dispatcher.dispatch(
            "application/json; charset=utf-8", b'{"a":1}', None
        )
        assert result.content_type == ContentType.APPLICATION_JSON

    @pytest.mark.asyncio
    async def test_parse_content_type(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        ct, raw = dispatcher._parse_content_type("multipart/form-data; boundary=abc")
        assert ct == ContentType.MULTIPART_FORM_DATA
        assert raw == "multipart/form-data"

    @pytest.mark.asyncio
    async def test_parse_content_type_with_boundary(self, mock_json_analyzer, mock_multipart_analyzer):
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        dispatcher = ContentTypeDispatcher(
            json_analyzer=mock_json_analyzer,
            multipart_analyzer=mock_multipart_analyzer,
        )
        ct, raw = dispatcher._parse_content_type(
            "multipart/form-data; boundary=----WebKitFormBoundary"
        )
        assert ct == ContentType.MULTIPART_FORM_DATA
        assert raw == "multipart/form-data"


class TestContentTypeMiddleware:
    @pytest.mark.asyncio
    async def test_returns_415_for_unknown_type(self):
        from anonreq.middleware.content_type import ContentTypeMiddleware
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        app = MagicMock()
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
        )
        middleware = ContentTypeMiddleware(app, dispatcher=dispatcher)

        scope = {
            "type": "http",
            "headers": [(b"content-type", b"application/xml")],
            "method": "POST",
            "path": "/v1/chat",
        }
        send = AsyncMock()
        receive = AsyncMock()
        await middleware(scope, receive, send)
        assert send.call_count >= 1
        first_call = send.call_args_list[0]
        args, _ = first_call
        message = args[0]
        assert message["type"] == "http.response.start"
        assert message["status"] == 415

    @pytest.mark.asyncio
    async def test_attaches_result_to_request_state(self):
        from anonreq.middleware.content_type import ContentTypeMiddleware
        from anonreq.multimodal.dispatcher import ContentTypeDispatcher

        app = AsyncMock()
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
        )
        middleware = ContentTypeMiddleware(app, dispatcher=dispatcher)

        scope = {
            "type": "http",
            "headers": [(b"content-type", b"text/plain")],
            "method": "POST",
            "path": "/v1/chat",
        }
        send = AsyncMock()
        receive = AsyncMock()
        await middleware(scope, receive, send)
        app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_through_without_dispatcher(self):
        from anonreq.middleware.content_type import ContentTypeMiddleware

        app = AsyncMock()
        middleware = ContentTypeMiddleware(app)

        scope = {
            "type": "http",
            "headers": [(b"content-type", b"text/plain")],
            "method": "POST",
            "path": "/v1/chat",
        }
        send = AsyncMock()
        receive = AsyncMock()
        await middleware(scope, receive, send)
        app.assert_awaited_once()
