"""Tests for MCP Inspector (Plan 17-02, Task 3).

Per D-007, D-008:
- inspect_request detects MCP content and extracts tool calls
- inspect_request returns None for non-MCP content
- mcp_content_type_detected matches MCP content types
"""

from __future__ import annotations

import json
import types

from anonreq.mcp.inspector import MCPInspector


class TestMCPInspector:
    """Test suite for MCPInspector."""

    def setup_method(self):
        from anonreq.discovery.flow_analyzer import FlowAnalyzer
        from anonreq.discovery.hostname_allowlist import HostnameAllowlist

        self.flow_analyzer = FlowAnalyzer()
        self.allowlist = HostnameAllowlist()
        self.inspector = MCPInspector(self.flow_analyzer, self.allowlist)

    def test_mcp_content_type_explicit_match(self):
        """mcp_content_type_detected matches explicit MCP content types."""
        assert self.inspector.mcp_content_type_detected("application/x-mcp") is True
        assert self.inspector.mcp_content_type_detected("application/vnd.mcp+json") is True

    def test_mcp_content_type_no_match(self):
        """mcp_content_type_detected returns False for non-MCP types."""
        assert self.inspector.mcp_content_type_detected("text/plain") is False
        assert self.inspector.mcp_content_type_detected("") is False

    def test_mcp_content_type_json_is_not_explicit(self):
        """application/json alone is not explicit MCP — needs body inspection."""
        assert self.inspector.mcp_content_type_detected("application/json") is False

    async def test_inspect_request_detects_tool_call(self):
        """inspect_request detects MCP tool calls from request body."""
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"location": "Paris"},
            },
        }).encode()

        request = _make_request(
            method="POST",
            path="/mcp",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Host": "api.anthropic.com",
            },
        )

        result = await self.inspector.inspect_request(request)
        assert result is not None
        assert result.detected is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"

    async def test_inspect_request_returns_none_for_non_mcp(self):
        """inspect_request returns None for non-MCP content."""
        body = json.dumps({"hello": "world"}).encode()

        request = _make_request(
            method="POST",
            path="/api",
            body=body,
            headers={"Content-Type": "application/json"},
        )

        result = await self.inspector.inspect_request(request)
        assert result is None

    async def test_inspect_request_returns_none_for_empty_body(self):
        """inspect_request returns None for empty body."""
        request = _make_request(method="POST", path="/mcp", body=b"", headers={})
        result = await self.inspector.inspect_request(request)
        assert result is None

    async def test_inspect_request_identifies_provider(self):
        """inspect_request identifies the AI provider from hostname."""
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"query": "test"}},
        }).encode()

        request = _make_request(
            method="POST",
            path="/mcp",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Host": "api.openai.com",
            },
        )

        result = await self.inspector.inspect_request(request)
        assert result is not None
        assert result.provider is not None

    async def test_inspect_request_detects_tool_results(self):
        """inspect_request detects tool results in response messages."""
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "name": "get_weather",
                "content": {"temperature": 22},
            },
        }).encode()

        request = _make_request(
            method="POST",
            path="/mcp",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Host": "api.anthropic.com",
            },
        )

        result = await self.inspector.inspect_request(request)
        assert result is not None
        assert result.detected is True
        assert len(result.tool_results) == 1
        assert result.tool_results[0].name == "get_weather"

    async def test_inspect_response_flags_suspicious_results(self):
        """inspect_response flags large/suspicious tool results."""
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "name": "read_file",
                "content": "A" * 20000,  # large content
            },
        }).encode()

        response = _make_response(body=body)
        session_ctx: dict = {}

        await self.inspector.inspect_response(response, session_ctx)
        assert "mcp_suspicious_results" in session_ctx

    async def test_inspect_response_noop_for_non_mcp(self):
        """inspect_response is no-op for non-MCP content."""
        body = json.dumps({"hello": "world"}).encode()
        response = _make_response(body=body)
        session_ctx: dict = {}

        await self.inspector.inspect_response(response, session_ctx)
        assert "mcp_suspicious_results" not in session_ctx

    async def test_inspect_request_batch_messages(self):
        """inspect_request handles batch MCP messages."""
        body = json.dumps([
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "tool_a", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "tool_b", "arguments": {}},
            },
        ]).encode()

        request = _make_request(
            method="POST",
            path="/mcp",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Host": "api.openai.com",
            },
        )

        result = await self.inspector.inspect_request(request)
        assert result is not None
        assert len(result.tool_calls) == 2


def _make_request(
    method: str = "GET",
    path: str = "/",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
):
    """Create a mock request-like object with async body()."""
    body_bytes = body or b""

    class MockRequest:
        def __init__(self):
            self.method = method
            self.url = types.SimpleNamespace()
            self.url.path = path
            self.url.host = headers.get("Host", "unknown") if headers else "unknown"
            self.headers = headers or {}
            self._body = body_bytes

        async def body(self):
            return self._body

    return MockRequest()


def _make_response(body: bytes | None = None):
    """Create a mock response-like object."""
    body_bytes = body or b""

    class MockResponse:
        def __init__(self):
            self._body = body_bytes

        async def body(self):
            return self._body

    return MockResponse()
