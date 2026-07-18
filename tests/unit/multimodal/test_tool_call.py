"""Unit tests for tool_call extraction functions."""

from __future__ import annotations

from typing import Any

import pytest

from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.tool_call import (
    ToolCallDetection,
    ToolCallExtractor,
    ToolCallResult,
    extract_tool_calls_anthropic,
    extract_tool_calls_mcp,
    extract_tool_calls_openai,
)


class StubDetectionEngine:
    def __init__(self, entities: list[dict[str, Any]] | None = None) -> None:
        self._entities = entities or []

    async def analyze_text(self, _value: str) -> list[dict[str, Any]]:
        return self._entities


@pytest.fixture
def analyzer_with_pii() -> JsonAnalyzer:
    engine = StubDetectionEngine(
        entities=[{"entity_type": "EMAIL", "start": 0, "end": 15, "score": 0.9}]
    )
    return JsonAnalyzer(detection_engine=engine)


@pytest.fixture
def analyzer_clean() -> JsonAnalyzer:
    return JsonAnalyzer(detection_engine=StubDetectionEngine(entities=[]))


@pytest.mark.unit
class TestToolCallDetection:
    def test_has_pii_true(self) -> None:
        d = ToolCallDetection(
            index=0,
            tool_call_id="tc-1",
            function_name="search",
            arguments={},
            entities=[{"entity_type": "SSN"}],
        )
        assert d.has_pii is True

    def test_has_pii_false(self) -> None:
        d = ToolCallDetection(
            index=0,
            tool_call_id="tc-1",
            function_name="search",
            arguments={},
            entities=[],
        )
        assert d.has_pii is False


@pytest.mark.unit
class TestToolCallResult:
    def test_total_entities(self) -> None:
        r = ToolCallResult(
            provider="openai",
            detections=[
                ToolCallDetection(0, None, "f", {}, [{"e": 1}]),
                ToolCallDetection(1, None, "g", {}, [{"e": 2}, {"e": 3}]),
            ],
        )
        assert r.total_entities == 3

    def test_has_pii(self) -> None:
        r = ToolCallResult(provider="openai", detections=[])
        assert r.has_pii is False


@pytest.mark.unit
class TestExtractOpenAI:
    @pytest.mark.anyio
    async def test_extracts_tool_calls(self, analyzer_with_pii: JsonAnalyzer) -> None:
        message = {
            "tool_calls": [
                {
                    "id": "tc-1",
                    "function": {
                        "name": "lookup_email",
                        "arguments": '{"email": "test@example.com"}',
                    },
                }
            ]
        }
        result = await extract_tool_calls_openai(message, analyzer_with_pii)
        assert result.provider == "openai"
        assert len(result.detections) >= 1
        assert result.has_pii

    @pytest.mark.anyio
    async def test_no_tool_calls(self, analyzer_clean: JsonAnalyzer) -> None:
        message: dict[str, Any] = {}
        result = await extract_tool_calls_openai(message, analyzer_clean)
        assert result.provider == "openai"
        assert len(result.detections) == 0

    @pytest.mark.anyio
    async def test_dict_arguments(self, analyzer_clean: JsonAnalyzer) -> None:
        message = {
            "tool_calls": [
                {
                    "id": "tc-2",
                    "function": {
                        "name": "get_weather",
                        "arguments": {"city": "NYC"},
                    },
                }
            ]
        }
        result = await extract_tool_calls_openai(message, analyzer_clean)
        assert result.provider == "openai"
        assert len(result.detections) == 1
        assert result.detections[0].arguments == {"city": "NYC"}


@pytest.mark.unit
class TestExtractAnthropic:
    @pytest.mark.anyio
    async def test_extracts_tool_use_blocks(self, analyzer_clean: JsonAnalyzer) -> None:
        content = [
            {"type": "text", "text": "Let me look that up."},
            {"type": "tool_use", "id": "tu-1", "name": "search", "input": {"q": "weather"}},
        ]
        result = await extract_tool_calls_anthropic(content, analyzer_clean)
        assert result.provider == "anthropic"
        assert len(result.detections) == 1
        assert result.detections[0].function_name == "search"


@pytest.mark.unit
class TestExtractMCP:
    @pytest.mark.anyio
    async def test_extracts_mcp_request(self, analyzer_clean: JsonAnalyzer) -> None:
        payload = {
            "method": "tools/call",
            "params": {"name": "read_file", "arguments": {"path": "/etc/passwd"}},
        }
        result = await extract_tool_calls_mcp(payload, analyzer_clean)
        assert result.provider == "mcp"
        assert len(result.detections) == 1

    @pytest.mark.anyio
    async def test_extracts_mcp_result(self, analyzer_clean: JsonAnalyzer) -> None:
        payload = {
            "result": {
                "content": [{"type": "text", "text": "file contents here"}],
            }
        }
        result = await extract_tool_calls_mcp(payload, analyzer_clean)
        assert result.provider == "mcp"


@pytest.mark.unit
class TestToolCallExtractor:
    @pytest.mark.anyio
    async def test_extract_request_openai(self, analyzer_clean: JsonAnalyzer) -> None:
        extractor = ToolCallExtractor(analyzer_clean)
        messages = [
            {
                "tool_calls": [
                    {
                        "id": "tc-1",
                        "function": {"name": "search", "arguments": '{"q": "test"}'},
                    }
                ]
            }
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "openai"

    @pytest.mark.anyio
    async def test_extract_request_anthropic(self, analyzer_clean: JsonAnalyzer) -> None:
        extractor = ToolCallExtractor(analyzer_clean)
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-1", "name": "calc", "input": {"x": 1}},
                ],
            }
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "anthropic"

    @pytest.mark.anyio
    async def test_extract_response_openai(self, analyzer_clean: JsonAnalyzer) -> None:
        extractor = ToolCallExtractor(analyzer_clean)
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"id": "tc-1", "function": {"name": "f", "arguments": "{}"}},
                        ]
                    }
                }
            ]
        }
        result = await extractor.extract_response(response, "openai")
        assert result.provider == "openai"
