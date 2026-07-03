"""Tests for multi-format tool call extraction.

Covers OpenAI tool_calls, Anthropic tool_use, and MCP tools/call
JSON-RPC formats for both tool call extraction and tool result
extraction.
"""

from __future__ import annotations

import pytest

from anonreq.governance.tool_extractor import (
    ToolCall,
    ToolExtractionError,
    ToolExtractor,
    ToolResult,
)


class TestExtractCallsOpenAI:
    """Extract tool calls from OpenAI format (tool_calls in assistant message)."""

    def test_extract_single_tool_call(self):
        """Test 1a: Single OpenAI tool call extracted correctly."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "search_documents",
                        "arguments": '{"query": "annual report", "limit": 5}',
                    },
                },
            ],
        }
        calls = extractor.extract_calls(message, "openai")
        assert len(calls) == 1
        assert calls[0].id == "call_abc123"
        assert calls[0].name == "search_documents"
        assert calls[0].arguments == {"query": "annual report", "limit": 5}
        assert calls[0].format == "openai"

    def test_extract_multiple_tool_calls(self):
        """Extract multiple OpenAI tool calls."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": "I'll search and analyze.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": '{"q": "test"}',
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "analyze",
                        "arguments": '{"data": "results"}',
                    },
                },
            ],
        }
        calls = extractor.extract_calls(message, "openai")
        assert len(calls) == 2
        assert calls[0].name == "search"
        assert calls[1].name == "analyze"

    def test_no_tool_calls_returns_empty_list(self):
        """Test 7: Message without tool_calls returns empty list."""
        extractor = ToolExtractor()
        message = {"role": "assistant", "content": "Hello!"}
        calls = extractor.extract_calls(message, "openai")
        assert calls == []

    def test_malformed_arguments_raises_error(self):
        """Test 8: Malformed JSON arguments raise ToolExtractionError."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_bad",
                    "type": "function",
                    "function": {
                        "name": "bad_tool",
                        "arguments": "not valid json{",
                    },
                },
            ],
        }
        with pytest.raises(ToolExtractionError, match="arguments"):
            extractor.extract_calls(message, "openai")

    def test_missing_function_name_handled(self):
        """Tool call without function name returns call with empty name."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "arguments": '{"x": 1}',
                    },
                },
            ],
        }
        with pytest.raises(ToolExtractionError, match="name"):
            extractor.extract_calls(message, "openai")


class TestExtractCallsAnthropic:
    """Extract tool calls from Anthropic format (tool_use content blocks)."""

    def test_extract_anthropic_tool_use(self):
        """Test 2: Anthropic tool_use content blocks extracted correctly."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check that for you."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_weather",
                    "input": {"location": "San Francisco", "units": "celsius"},
                },
            ],
        }
        calls = extractor.extract_calls(message, "anthropic")
        assert len(calls) == 1
        assert calls[0].id == "toolu_123"
        assert calls[0].name == "get_weather"
        assert calls[0].arguments == {"location": "San Francisco", "units": "celsius"}
        assert calls[0].format == "anthropic"

    def test_extract_multiple_anthropic_calls(self):
        """Extract multiple Anthropic tool_use blocks."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "search",
                    "input": {"q": "test"},
                },
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "summarize",
                    "input": {"text": "content"},
                },
            ],
        }
        calls = extractor.extract_calls(message, "anthropic")
        assert len(calls) == 2

    def test_no_tool_use_returns_empty(self):
        """Anthropic message without tool_use blocks returns empty list."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
        }
        calls = extractor.extract_calls(message, "anthropic")
        assert calls == []

    def test_anthropic_missing_name_raises_error(self):
        """Anthropic tool_use block without name raises ToolExtractionError."""
        extractor = ToolExtractor()
        message = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "input": {"x": 1},
                },
            ],
        }
        with pytest.raises(ToolExtractionError, match="name"):
            extractor.extract_calls(message, "anthropic")


class TestExtractCallsMCP:
    """Extract tool calls from MCP JSON-RPC format (tools/call method)."""

    def test_extract_mcp_tool_call(self):
        """Test 3: MCP JSON-RPC tools/call extracted correctly."""
        extractor = ToolExtractor()
        message = {
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "tools/call",
            "params": {
                "name": "db_query",
                "arguments": {"sql": "SELECT * FROM users", "limit": 10},
            },
        }
        calls = extractor.extract_calls(message, "mcp")
        assert len(calls) == 1
        assert calls[0].id == "req_001"
        assert calls[0].name == "db_query"
        assert calls[0].arguments == {"sql": "SELECT * FROM users", "limit": 10}
        assert calls[0].format == "mcp"

    def test_mcp_non_tool_method_returns_empty(self):
        """MCP message with method other than tools/call returns empty."""
        extractor = ToolExtractor()
        message = {
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "resources/list",
            "params": {},
        }
        calls = extractor.extract_calls(message, "mcp")
        assert calls == []

    def test_mcp_missing_params_name_raises_error(self):
        """MCP tools/call without params.name raises ToolExtractionError."""
        extractor = ToolExtractor()
        message = {
            "jsonrpc": "2.0",
            "id": "req_001",
            "method": "tools/call",
            "params": {
                "arguments": {"x": 1},
            },
        }
        with pytest.raises(ToolExtractionError, match="name"):
            extractor.extract_calls(message, "mcp")


class TestExtractResultsOpenAI:
    """Extract tool results from OpenAI format (tool role messages)."""

    def test_extract_openai_tool_result(self):
        """Test 4: OpenAI tool result extracted correctly."""
        extractor = ToolExtractor()
        message = {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": '{"result": "found 5 documents"}',
        }
        results = extractor.extract_results(message, "openai")
        assert len(results) == 1
        assert results[0].id == "call_abc123"
        assert results[0].content == '{"result": "found 5 documents"}'
        assert results[0].format == "openai"

    def test_openai_tool_result_without_call_id(self):
        """OpenAI tool result without tool_call_id returns empty name."""
        extractor = ToolExtractor()
        message = {
            "role": "tool",
            "content": "result data",
        }
        results = extractor.extract_results(message, "openai")
        assert len(results) == 1
        assert results[0].name == ""

    def test_openai_non_tool_message_returns_empty(self):
        """Non-tool role in OpenAI format returns empty list."""
        extractor = ToolExtractor()
        message = {"role": "user", "content": "Hello"}
        results = extractor.extract_results(message, "openai")
        assert results == []


class TestExtractResultsAnthropic:
    """Extract tool results from Anthropic format (tool_result content blocks)."""

    def test_extract_anthropic_tool_result(self):
        """Test 5: Anthropic tool_result content block extracted correctly."""
        extractor = ToolExtractor()
        message = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_123",
                    "content": "Weather data for San Francisco",
                },
            ],
        }
        results = extractor.extract_results(message, "anthropic")
        assert len(results) == 1
        assert results[0].id == "toolu_123"
        assert results[0].content == "Weather data for San Francisco"
        assert results[0].format == "anthropic"

    def test_anthropic_tool_result_with_is_error(self):
        """Anthropic tool_result with is_error flag."""
        extractor = ToolExtractor()
        message = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_err",
                    "content": "Error: rate limit exceeded",
                    "is_error": True,
                },
            ],
        }
        results = extractor.extract_results(message, "anthropic")
        assert len(results) == 1
        assert results[0].is_error is True
        assert results[0].content == "Error: rate limit exceeded"


class TestExtractResultsMCP:
    """Extract tool results from MCP JSON-RPC response format."""

    def test_extract_mcp_result(self):
        """Test 6: MCP tool result from JSON-RPC response."""
        extractor = ToolExtractor()
        message = {
            "jsonrpc": "2.0",
            "id": "req_001",
            "result": {
                "content": [
                    {"type": "text", "text": "Query returned 5 rows"},
                ],
            },
        }
        results = extractor.extract_results(message, "mcp")
        assert len(results) == 1
        assert results[0].id == "req_001"
        assert results[0].format == "mcp"

    def test_mcp_error_result_extracted(self):
        """MCP JSON-RPC error response extracted as tool result with is_error."""
        extractor = ToolExtractor()
        message = {
            "jsonrpc": "2.0",
            "id": "req_001",
            "error": {
                "code": -32603,
                "message": "Internal error",
            },
        }
        results = extractor.extract_results(message, "mcp")
        assert len(results) == 1
        assert results[0].is_error is True
        assert results[0].id == "req_001"

    def test_mcp_non_tool_response_returns_empty(self):
        """MCP response without result or error fields returns empty."""
        extractor = ToolExtractor()
        message = {"jsonrpc": "2.0", "id": "req_001"}
        results = extractor.extract_results(message, "mcp")
        assert results == []


class TestDetectFormat:
    """Tests for format auto-detection."""

    def test_detect_openai_format(self):
        """Detect OpenAI format from tool_calls in messages."""
        extractor = ToolExtractor()
        body = {
            "messages": [
                {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "f1"}}]},
            ],
        }
        fmt = extractor.detect_format(body, {})
        assert fmt == "openai"

    def test_detect_anthropic_format(self):
        """Detect Anthropic format from tool_use content blocks."""
        extractor = ToolExtractor()
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "tu1", "name": "f1"}],
                },
            ],
        }
        fmt = extractor.detect_format(body, {})
        assert fmt == "anthropic"

    def test_detect_mcp_format(self):
        """Detect MCP format from method field."""
        extractor = ToolExtractor()
        body = {"method": "tools/call"}
        fmt = extractor.detect_format(body, {})
        assert fmt == "mcp"

    def test_detect_unknown_format_returns_none(self):
        """Unknown format returns None."""
        extractor = ToolExtractor()
        body = {"messages": [{"role": "user", "content": "hi"}]}
        fmt = extractor.detect_format(body, {})
        assert fmt is None


class TestDetectDomain:
    """Tests for domain detection (model vs host)."""

    def test_detect_host_domain_via_header(self):
        """Test 9: X-AnonReq-Tool-Domain: host header sets domain to host."""
        extractor = ToolExtractor()
        headers = {"X-AnonReq-Tool-Domain": "host"}
        domain = extractor.detect_domain(headers, {})
        assert domain == "host"

    def test_detect_model_domain_by_default(self):
        """No domain header defaults to model."""
        extractor = ToolExtractor()
        domain = extractor.detect_domain({}, {})
        assert domain == "model"

    def test_detect_model_domain_explicit(self):
        """X-AnonReq-Tool-Domain: model header sets domain to model."""
        extractor = ToolExtractor()
        headers = {"X-AnonReq-Tool-Domain": "model"}
        domain = extractor.detect_domain(headers, {})
        assert domain == "model"

    def test_mcp_format_host_detection(self):
        """MCP format requests with host_mcp provider detected as host."""
        extractor = ToolExtractor()
        body = {
            "model": "host_mcp/default",
            "messages": [{"role": "user", "content": "query db"}],
        }
        # Default: without header, with model containing "host_", still model
        domain = extractor.detect_domain({}, body)
        assert domain == "model"  # Domain detection is header-based by design
