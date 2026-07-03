"""Tests for AI traffic detection and MCP inspection."""

from __future__ import annotations

import json

import pytest

from anonreq.gateway.detector import (
    AIDetector,
    MCPInspector,
    MCPMessage,
    ProviderMatch,
    TrafficClassification,
)


class TestAIDetector:
    """Tests for AIDetector — hostname/pattern-based AI provider detection."""

    @pytest.fixture
    def detector(self):
        return AIDetector()

    def test_detect_openai_hostname(self, detector):
        result = detector.detect_hostname("api.openai.com")
        assert result is not None
        assert result.provider == "openai"
        assert result.confidence >= 0.9

    def test_detect_anthropic_hostname(self, detector):
        result = detector.detect_hostname("api.anthropic.com")
        assert result is not None
        assert result.provider == "anthropic"

    def test_detect_gemini_hostname(self, detector):
        result = detector.detect_hostname("generativelanguage.googleapis.com")
        assert result is not None
        assert result.provider == "gemini"

    def test_detect_ollama_hostname(self, detector):
        result = detector.detect_hostname("localhost:11434")
        assert result is not None
        assert result.provider == "ollama"

    def test_detect_unknown_hostname(self, detector):
        result = detector.detect_hostname("example.com")
        assert result is None

    def test_detect_openai_subdomain(self, detector):
        result = detector.detect_hostname("api.openai.com")
        assert result is not None
        assert result.provider == "openai"

    def test_detect_deepseek_hostname(self, detector):
        result = detector.detect_hostname("api.deepseek.com")
        assert result is not None
        assert result.provider == "deepseek"

    def test_detect_custom_with_hostname_pattern(self):
        detector = AIDetector(custom_patterns={"myai": ["my-ai.company.com"]})
        result = detector.detect_hostname("my-ai.company.com")
        assert result is not None
        assert result.provider == "myai"

    def test_classify_request_with_openai_path(self, detector):
        result = detector.classify_request(
            method="POST",
            path="/v1/chat/completions",
            host="api.openai.com",
        )
        assert result.is_ai_traffic is True
        assert result.provider == "openai"
        assert result.endpoint_type == "chat_completion"

    def test_classify_request_embeddings(self, detector):
        result = detector.classify_request(
            method="POST",
            path="/v1/embeddings",
            host="api.openai.com",
        )
        assert result.is_ai_traffic is True
        assert result.provider == "openai"
        assert result.endpoint_type == "embedding"

    def test_classify_request_anthropic_messages(self, detector):
        result = detector.classify_request(
            method="POST",
            path="/v1/messages",
            host="api.anthropic.com",
        )
        assert result.is_ai_traffic is True
        assert result.provider == "anthropic"
        assert result.endpoint_type == "messages"

    def test_classify_request_non_ai(self, detector):
        result = detector.classify_request(
            method="GET",
            path="/api/v1/users",
            host="internal.company.com",
        )
        assert result.is_ai_traffic is False
        assert result.provider is None

    def test_classify_request_by_payload_pattern(self, detector):
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        })
        result = detector.classify_request(
            method="POST",
            path="/some/proxy/path",
            host="proxy.internal",
            body=body,
        )
        assert result.is_ai_traffic is True
        assert result.provider == "openai"

    def test_classify_request_by_model_pattern(self, detector):
        body = json.dumps({
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": "hello"}],
        })
        result = detector.classify_request(
            method="POST",
            path="/v1/chat/completions",
            host="proxy.internal",
            body=body,
        )
        assert result.is_ai_traffic is True
        assert result.provider == "anthropic"


class TestAIDetectorBlockAllUnintercepted:
    """Tests for the block-all-unintercepted-AI policy flag."""

    @pytest.fixture
    def detector(self):
        return AIDetector()

    def test_known_provider_is_not_unintercepted(self, detector):
        result = detector.classify_request(
            method="POST",
            path="/v1/chat/completions",
            host="api.openai.com",
        )
        assert result.is_ai_traffic is True
        assert result.provider == "openai"
        assert result.detected_by_hostname is True

    def test_unidentified_ai_body_is_still_ai_traffic(self, detector):
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "test"}],
        })
        result = detector.classify_request(
            method="POST",
            path="/custom/path",
            host="custom-model.internal",
            body=body,
        )
        assert result.is_ai_traffic is True
        assert result.provider == "openai"
        assert result.detected_by_hostname is False

    def test_non_ai_traffic_is_not_intercepted(self, detector):
        result = detector.classify_request(
            method="GET",
            path="/static/file.js",
            host="cdn.example.com",
        )
        assert result.is_ai_traffic is False
        assert result.provider is None


class TestMCPInspector:
    """Tests for MCP protocol message inspection."""

    @pytest.fixture
    def inspector(self):
        return MCPInspector()

    def test_parse_valid_mcp_request(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "London"}},
            "id": 1,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.jsonrpc == "2.0"
        assert msg.method == "tools/call"
        assert msg.params == {"name": "get_weather", "arguments": {"city": "London"}}
        assert msg.msg_id == 1

    def test_parse_valid_mcp_notification(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.method == "notifications/initialized"
        assert msg.msg_id is None

    def test_parse_valid_mcp_response(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "result data"}]},
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.msg_id == 1
        assert msg.result == {"content": [{"type": "text", "text": "result data"}]}

    def test_parse_valid_mcp_error(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.msg_id == 1
        assert msg.error is not None
        assert msg.error["code"] == -32601

    def test_parse_invalid_json_returns_none(self, inspector):
        msg = inspector.parse("not json at all")
        assert msg is None

    def test_parse_invalid_mcp_missing_jsonrpc(self, inspector):
        raw = json.dumps({"method": "test", "id": 1})
        msg = inspector.parse(raw)
        assert msg is None

    def test_is_mcp_request_true(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "test"},
            "id": 1,
        })
        assert inspector.is_mcp(raw) is True

    def test_is_mcp_request_false(self, inspector):
        raw = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert inspector.is_mcp(raw) is False

    def test_is_mcp_invalid_json(self, inspector):
        assert inspector.is_mcp("not json") is False

    def test_detect_mcp_method_tools_call(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "get_data"},
            "id": 1,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.method_category == "tools"
        assert msg.method_name == "call"

    def test_detect_mcp_method_resources(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {"uri": "file:///data.txt"},
            "id": 2,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.method_category == "resources"
        assert msg.method_name == "read"

    def test_detect_mcp_method_prompts(self, inspector):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {"name": "greeting"},
            "id": 3,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.method_category == "prompts"
        assert msg.method_name == "get"

    def test_detect_tool_use_in_request_body(self, inspector):
        body = json.dumps({
            "model": "claude-opus-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Let me check the weather",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "London"}',
                            },
                        }
                    ],
                }
            ],
        })
        assert inspector.contains_tool_calls(body) is True

    def test_no_tool_use_in_request_body(self, inspector):
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert inspector.contains_tool_calls(body) is False

    def test_extract_tool_names(self, inspector):
        body = json.dumps({
            "model": "claude-opus-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": "{}"},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "send_email", "arguments": "{}"},
                        },
                    ],
                }
            ],
        })
        names = inspector.extract_tool_names(body)
        assert "get_weather" in names
        assert "send_email" in names
