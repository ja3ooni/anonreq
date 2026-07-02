from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from anonreq.multimodal.json_analyzer import JsonAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_json_analyzer():
    """Create a mock JsonAnalyzer that detects PII in string values.

    Returns an AsyncMock whose ``analyze`` method detects names and emails
    in string values, returning a ``UnifiedDetectionResult`` with populated
    ``entities``.
    """
    m = AsyncMock(spec=JsonAnalyzer)

    async def analyze_side_effect(json_data, path="$"):
        from anonreq.multimodal.models import ContentType, UnifiedDetectionResult

        result = UnifiedDetectionResult(content_type=ContentType.APPLICATION_JSON)

        if isinstance(json_data, dict):
            entities: list[dict] = []
            await _mock_walk(json_data, "$", 0, entities)
            result.entities = entities
        elif isinstance(json_data, str):
            try:
                parsed = json.loads(json_data)
                entities = []
                await _mock_walk(parsed, "$", 0, entities)
                result.entities = entities
            except (json.JSONDecodeError, ValueError):
                pass

        return result

    m.analyze = AsyncMock(side_effect=analyze_side_effect)
    return m


async def _mock_walk(node, path: str, depth: int, entities: list[dict]) -> None:
    """Walk a dict/list tree and detect emails / names in string leaves."""
    if depth > 20:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if isinstance(value, str):
                _detect_in_value(value, child, entities)
            else:
                await _mock_walk(value, child, depth + 1, entities)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            child = f"{path}[{i}]"
            if isinstance(item, str):
                _detect_in_value(item, child, entities)
            else:
                await _mock_walk(item, child, depth + 1, entities)


def _detect_in_value(value: str, path: str, entities: list[dict]) -> None:
    if "@" in value and "." in value.split("@")[-1]:
        entities.append({
            "entity_type": "EMAIL_ADDRESS",
            "start": 0,
            "end": len(value),
            "score": 0.98,
            "value": value,
            "json_path": path,
        })
    if any(name in value for name in ("John", "Alice", "Bob", "Jane")):
        entities.append({
            "entity_type": "PERSON",
            "start": value.find("John") if "John" in value
                       else value.find("Alice") if "Alice" in value
                       else value.find("Bob") if "Bob" in value
                       else value.find("Jane"),
            "end": (value.find("John") + 4) if "John" in value
                   else (value.find("Alice") + 5) if "Alice" in value
                   else (value.find("Bob") + 3) if "Bob" in value
                   else (value.find("Jane") + 4),
            "score": 0.95,
            "value": value,
            "json_path": path,
        })


# ---------------------------------------------------------------------------
# Helper to assert entity presence in a ToolCallResult
# ---------------------------------------------------------------------------

def _assert_has_entity(result, entity_type: str, *, index: int = 0) -> None:
    """Assert a detection exists for a given entity type at a tool-call index."""
    assert result.detections, "No detections in result"
    det = result.detections[index]
    types = {e["entity_type"] for e in det.entities}
    assert entity_type in types, (
        f"Expected entity {entity_type!r} at index {index}, "
        f"got {types}"
    )


# ===================================================================
# TASK 1 — OpenAI tool_calls
# ===================================================================

class TestExtractToolCallsOpenAI:
    """extract_tool_calls_openai — OpenAI tool_calls argument extraction."""

    @pytest.mark.asyncio
    async def test_extracts_and_analyzes_tool_call_arguments(
        self, mock_json_analyzer,
    ):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "send_email",
                        "arguments": json.dumps({
                            "recipient": "alice@example.com",
                            "subject": "Hello",
                            "body": "Hi Alice, your order is ready",
                        }),
                    },
                },
            ],
        }

        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert result.provider == "openai"
        assert len(result.detections) == 1
        assert result.detections[0].index == 0
        assert result.detections[0].tool_call_id == "call_abc123"
        assert result.detections[0].function_name == "send_email"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)
        _assert_has_entity(result, "PERSON", index=0)

    @pytest.mark.asyncio
    async def test_handles_null_tool_calls(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {"role": "assistant", "content": "Hello", "tool_calls": None}
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert result.provider == "openai"
        assert len(result.detections) == 0
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_handles_missing_tool_calls_key(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {"role": "assistant", "content": "Hello"}
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert result.provider == "openai"
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_handles_malformed_arguments_json(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_bad",
                    "type": "function",
                    "function": {
                        "name": "bad_func",
                        "arguments": "{invalid json}",
                    },
                },
            ],
        }
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert result.provider == "openai"
        # Malformed args still results in a detection entry with empty entities
        assert len(result.detections) == 1
        assert result.detections[0].entities == []
        assert result.detections[0].has_pii is False

    @pytest.mark.asyncio
    async def test_handles_empty_tool_calls_array(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [],
        }
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert result.provider == "openai"
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_preserves_tool_call_structure(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        args = {"city": "Berlin", "zip": "10115"}
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_preserve",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": json.dumps(args),
                    },
                },
            ],
        }
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert len(result.detections) == 1
        # Arguments should be preserved as a dict
        assert result.detections[0].arguments == args
        # No PII in these values
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "send_email",
                        "arguments": json.dumps({"to": "bob@example.com"}),
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_info",
                        "arguments": json.dumps({"query": "weather"}),
                    },
                },
            ],
        }
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert len(result.detections) == 2
        assert result.detections[0].has_pii is True   # bob@example.com
        assert result.detections[1].has_pii is False  # "weather" — no PII
        assert result.detections[0].tool_call_id == "call_1"
        assert result.detections[1].tool_call_id == "call_2"
        assert result.detections[0].function_name == "send_email"
        assert result.detections[1].function_name == "get_info"

    @pytest.mark.asyncio
    async def test_handles_non_dict_arguments(self, mock_json_analyzer):
        """Arguments that parse to non-dict (e.g. a string) are tolerated."""
        from anonreq.multimodal.tool_call import extract_tool_calls_openai

        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_str",
                    "type": "function",
                    "function": {
                        "name": "echo",
                        "arguments": json.dumps("just a string"),
                    },
                },
            ],
        }
        result = await extract_tool_calls_openai(message, mock_json_analyzer)

        assert len(result.detections) == 1
        assert result.detections[0].has_pii is False
        assert result.detections[0].arguments == "just a string"


# ===================================================================
# TASK 2 — Anthropic tool_use
# ===================================================================

class TestExtractToolCallsAnthropic:
    """extract_tool_calls_anthropic — Anthropic tool_use block extraction."""

    @pytest.mark.asyncio
    async def test_extracts_and_analyzes_tool_use_blocks(
        self, mock_json_analyzer,
    ):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        content = [
            {"type": "text", "text": "Let me look that up."},
            {
                "type": "tool_use",
                "id": "tu_001",
                "name": "lookup_user",
                "input": {
                    "email": "john@example.com",
                    "name": "John Doe",
                },
            },
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert result.provider == "anthropic"
        assert len(result.detections) == 1
        assert result.detections[0].index == 1  # position in content array
        assert result.detections[0].tool_call_id == "tu_001"
        assert result.detections[0].function_name == "lookup_user"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_handles_empty_content(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        result = await extract_tool_calls_anthropic([], mock_json_analyzer)

        assert result.provider == "anthropic"
        assert len(result.detections) == 0
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_ignores_non_tool_use_blocks(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        content = [
            {"type": "text", "text": "Hello"},
            {"type": "image", "source": {"type": "base64", "data": "deadbeef"}},
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert result.provider == "anthropic"
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_handles_missing_input_field(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        content = [
            {
                "type": "tool_use",
                "id": "tu_no_input",
                "name": "noop",
                # missing "input" key
            },
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert len(result.detections) == 1
        assert result.detections[0].arguments == {}
        assert result.detections[0].has_pii is False

    @pytest.mark.asyncio
    async def test_handles_null_input(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        content = [
            {
                "type": "tool_use",
                "id": "tu_null",
                "name": "noop",
                "input": None,
            },
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert len(result.detections) == 1
        assert result.detections[0].arguments == {}
        assert result.detections[0].has_pii is False

    @pytest.mark.asyncio
    async def test_multiple_tool_use_blocks(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        content = [
            {
                "type": "tool_use",
                "id": "tu_01",
                "name": "get_user",
                "input": {"user_id": 42},
            },
            {
                "type": "tool_use",
                "id": "tu_02",
                "name": "send_msg",
                "input": {"to": "bob@example.com", "text": "hello"},
            },
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert len(result.detections) == 2
        assert result.detections[0].has_pii is False
        assert result.detections[1].has_pii is True
        assert result.detections[0].tool_call_id == "tu_01"
        assert result.detections[1].tool_call_id == "tu_02"

    @pytest.mark.asyncio
    async def test_preserves_tool_use_structure(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_anthropic

        input_dict = {"city": "London", "units": "metric"}
        content = [
            {
                "type": "tool_use",
                "id": "tu_preserve",
                "name": "get_weather",
                "input": input_dict,
            },
        ]
        result = await extract_tool_calls_anthropic(content, mock_json_analyzer)

        assert len(result.detections) == 1
        assert result.detections[0].arguments == input_dict


# ===================================================================
# TASK 3 — MCP
# ===================================================================

class TestExtractToolCallsMCP:
    """extract_tool_calls_mcp — MCP tool/result payload extraction."""

    @pytest.mark.asyncio
    async def test_extracts_tools_call_method(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "lookup_user",
                "arguments": {
                    "email": "alice@example.com",
                    "name": "Alice Smith",
                },
            },
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) == 1
        assert result.detections[0].index == 0
        assert result.detections[0].function_name == "lookup_user"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_extracts_tools_result(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "Customer name is John Smith"},
                    {"type": "resource", "resource": {"uri": "db://users/1"}},
                ],
                "isError": False,
            },
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) >= 1
        assert result.has_pii is True

    @pytest.mark.asyncio
    async def test_ignores_non_tool_methods(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        # "resources/list" is not a tool method
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) == 0
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_handles_missing_params(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            # missing "params"
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_handles_null_arguments(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "noop",
                "arguments": None,
            },
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) == 1
        assert result.detections[0].arguments == {}
        assert result.detections[0].has_pii is False

    @pytest.mark.asyncio
    async def test_handles_result_without_content(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"isError": False},
        }
        result = await extract_tool_calls_mcp(payload, mock_json_analyzer)

        assert result.provider == "mcp"
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_preserves_mcp_top_level_structure(self, mock_json_analyzer):
        """The extractor must not mutate the original payload."""
        from anonreq.multimodal.tool_call import extract_tool_calls_mcp

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "hello"},
            },
        }
        original = json.dumps(payload, sort_keys=True)
        await extract_tool_calls_mcp(payload, mock_json_analyzer)
        assert json.dumps(payload, sort_keys=True) == original


# ===================================================================
# TASK 4 — ToolCallExtractor
# ===================================================================

class TestToolCallExtractor:
    """ToolCallExtractor — auto-detect provider format."""

    @pytest.mark.asyncio
    async def test_detects_openai_format(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        messages = [
            {"role": "user", "content": "lookup user"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "lookup",
                            "arguments": json.dumps({"email": "bob@test.com"}),
                        },
                    },
                ],
            },
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "openai"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_detects_anthropic_format(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        messages = [
            {"role": "user", "content": "lookup user"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Sure!"},
                    {
                        "type": "tool_use",
                        "id": "tu_01",
                        "name": "find_user",
                        "input": {"email": "jane@example.com"},
                    },
                ],
            },
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "anthropic"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_detects_mcp_format(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "lookup",
                    "arguments": {"email": "alice@example.com"},
                },
            },
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "mcp"
        assert result.has_pii is True

    @pytest.mark.asyncio
    async def test_detects_mcp_result_format(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": "John data"}],
                },
            },
        ]
        result = await extractor.extract_request(messages)
        assert result.provider == "mcp"
        assert result.has_pii is True

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_empty(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = await extractor.extract_request(messages)
        assert len(result.detections) == 0
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_empty_messages(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        result = await extractor.extract_request([])
        assert len(result.detections) == 0
        assert result.has_pii is False

    @pytest.mark.asyncio
    async def test_extract_response_openai(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_resp",
                                "type": "function",
                                "function": {
                                    "name": "process",
                                    "arguments": json.dumps({
                                        "email": "bob@example.com",
                                    }),
                                },
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
        }
        result = await extractor.extract_response(response, provider="openai")
        assert result.provider == "openai"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_extract_response_anthropic(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        response = {
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_resp",
                    "name": "lookup",
                    "input": {"email": "john@example.com"},
                },
            ],
            "model": "claude-3-opus",
            "stop_reason": "end_turn",
        }
        result = await extractor.extract_response(response, provider="anthropic")
        assert result.provider == "anthropic"
        assert result.has_pii is True
        _assert_has_entity(result, "EMAIL_ADDRESS", index=0)

    @pytest.mark.asyncio
    async def test_extract_response_mcp(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "Bob Johnson's data"},
                ],
                "isError": False,
            },
        }
        result = await extractor.extract_response(response, provider="mcp")
        assert result.provider == "mcp"
        assert result.has_pii is True

    @pytest.mark.asyncio
    async def test_extract_response_unknown_provider(self, mock_json_analyzer):
        from anonreq.multimodal.tool_call import ToolCallExtractor

        extractor = ToolCallExtractor(mock_json_analyzer)
        result = await extractor.extract_response({"foo": "bar"}, provider="unknown")
        assert len(result.detections) == 0
        assert result.has_pii is False
