"""Tests for MCP JSON-RPC 2.0 message parser (Plan 17-02, Task 3).

Per D-007, D-008:
- Parse valid MCP tool call message
- Parse MCP batch message (list)
- extract_tool_calls returns correct name, arguments, id
- extract_tool_results returns correct content
- Malformed message raises MCPParseError
- is_mcp_message correctly identifies MCP vs non-MCP content
"""

from __future__ import annotations

import json

import pytest

from anonreq.mcp.parser import MCPMessage, MCPParseError, MCPParser


class TestMCPParser:
    """Test suite for MCPParser."""

    def setup_method(self):
        self.parser = MCPParser()

    def test_parse_single_tool_call(self):
        """Parse a valid single MCP tools/call message."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"location": "San Francisco", "unit": "celsius"},
            },
        })
        result = self.parser.parse(raw)
        assert isinstance(result, MCPMessage)
        assert result.jsonrpc == "2.0"
        assert result.id == 1
        assert result.method == "tools/call"
        assert result.params == {"name": "get_weather", "arguments": {"location": "San Francisco", "unit": "celsius"}}  # noqa: E501

    def test_parse_batch_messages(self):
        """Parse a batch (list) of MCP messages."""
        raw = json.dumps([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tool1"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tool2"}},
        ])
        result = self.parser.parse(raw)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    def test_parse_response_message(self):
        """Parse a valid MCP response (result, no method)."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"name": "get_weather", "content": {"temperature": 22}},
        })
        result = self.parser.parse(raw)
        assert isinstance(result, MCPMessage)
        assert result.result == {"name": "get_weather", "content": {"temperature": 22}}
        assert result.method is None

    def test_parse_invalid_json_raises_error(self):
        """Malformed JSON raises MCPParseError."""
        with pytest.raises(MCPParseError, match="Invalid JSON"):
            self.parser.parse(b"{invalid json}")

    def test_parse_missing_jsonrpc_field_raises_error(self):
        """Missing jsonrpc field raises MCPParseError."""
        raw = json.dumps({"id": 1, "method": "tools/call"})
        with pytest.raises(MCPParseError, match="Invalid jsonrpc version"):
            self.parser.parse(raw)

    def test_parse_wrong_jsonrpc_version_raises_error(self):
        """Wrong jsonrpc version raises MCPParseError."""
        raw = json.dumps({"jsonrpc": "1.0", "id": 1, "method": "tools/call"})
        with pytest.raises(MCPParseError, match="Invalid jsonrpc version"):
            self.parser.parse(raw)

    def test_extract_tool_calls_from_message(self):
        """Extract tool calls from a tools/call message."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"location": "Paris"},
            },
        })
        message = self.parser.parse(raw)
        calls = self.parser.extract_tool_calls(message)
        assert len(calls) == 1
        assert calls[0].name == "get_weather"
        assert calls[0].arguments == {"location": "Paris"}
        assert calls[0].id == "1"
        assert calls[0].domain == "model"

    def test_extract_tool_calls_no_method_returns_empty(self):
        """Message without method returns empty tool calls list."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": "ok"},
        })
        message = self.parser.parse(raw)
        calls = self.parser.extract_tool_calls(message)
        assert len(calls) == 0

    def test_extract_tool_results_from_response(self):
        """Extract tool results from a tools/call response."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "name": "get_weather",
                "content": {"temperature": 22, "conditions": "sunny"},
            },
        })
        message = self.parser.parse(raw)
        results = self.parser.extract_tool_results(message)
        assert len(results) == 1
        assert results[0].name == "get_weather"
        assert results[0].content == {"temperature": 22, "conditions": "sunny"}
        assert results[0].is_error is False

    def test_extract_tool_results_with_error(self):
        """Extract tool results with error flag."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "name": "get_weather",
                "content": "API rate limit exceeded",
                "isError": True,
            },
        })
        message = self.parser.parse(raw)
        results = self.parser.extract_tool_results(message)
        assert len(results) == 1
        assert results[0].is_error is True
        assert results[0].content == "API rate limit exceeded"

    def test_extract_tool_results_no_result_returns_empty(self):
        """Message without result returns empty tool results list."""
        raw = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {},
        })
        message = self.parser.parse(raw)
        results = self.parser.extract_tool_results(message)
        assert len(results) == 0

    def test_is_mcp_message_true(self):
        """is_mcp_message returns True for valid MCP data."""
        data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call"}).encode()
        assert self.parser.is_mcp_message(data) is True

    def test_is_mcp_message_batch(self):
        """is_mcp_message returns True for batch MCP data."""
        data = json.dumps([
            {"jsonrpc": "2.0", "id": 1},
            {"jsonrpc": "2.0", "id": 2},
        ]).encode()
        assert self.parser.is_mcp_message(data) is True

    def test_is_mcp_message_false_for_non_json(self):
        """is_mcp_message returns False for non-JSON data."""
        data = b"Hello, World!"
        assert self.parser.is_mcp_message(data) is False

    def test_is_mcp_message_false_for_non_mcp_json(self):
        """is_mcp_message returns False for JSON without jsonrpc field."""
        data = json.dumps({"hello": "world"}).encode()
        assert self.parser.is_mcp_message(data) is False

    def test_is_mcp_message_empty(self):
        """is_mcp_message returns False for empty data."""
        assert self.parser.is_mcp_message(b"") is False

    def test_serialize_roundtrip(self):
        """Serializing and re-parsing produces the same data."""
        original = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "test", "arguments": {"key": "val"}},
        }
        message = self.parser.parse(json.dumps(original))
        serialized = self.parser.serialize(message)
        reparsed = self.parser.parse(serialized)
        assert reparsed.id == 5
        assert reparsed.method == "tools/call"

    def test_extract_tool_calls_from_batch(self):
        """Extract tool calls from a batch of messages."""
        raw = json.dumps([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tool_a"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tool_b"}},
        ])
        messages = self.parser.parse(raw)
        calls = self.parser.extract_tool_calls(messages)
        assert len(calls) == 2
        assert calls[0].name == "tool_a"
        assert calls[1].name == "tool_b"

    def test_parse_handles_bytes_input(self):
        """Parse accepts bytes input."""
        raw = b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"test"}}'
        result = self.parser.parse(raw)
        assert isinstance(result, MCPMessage)
        assert result.method == "tools/call"
