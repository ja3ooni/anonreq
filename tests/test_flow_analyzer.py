"""Tests for flow analysis heuristics (Plan 17-02, Task 2).

Per D-007, D-008, D-010, D-011:
- FlowAnalyzer detects chat completion endpoint patterns in request paths
- FlowAnalyzer detects AI API key patterns in request headers
- FlowAnalyzer detects large request bodies typical of LLM prompts
- FlowAnalyzer assigns confidence score to detection
- FlowAnalyzer returns None for non-matching traffic
"""

from __future__ import annotations

import json

import pytest


class TestFlowAnalyzer:
    """Test suite for FlowAnalyzer."""

    def setup_method(self):
        from anonreq.discovery.flow_analyzer import FlowAnalyzer
        self.analyzer = FlowAnalyzer()

    def test_path_detection_chat_completions(self):
        """Detect chat completion endpoint by path pattern."""
        from anonreq.discovery.flow_analyzer import FlowResult

        request = _make_request(method="POST", path="/v1/chat/completions")
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.0
        assert any("path" in i.lower() for i in result.indicators)

    def test_path_detection_messages(self):
        """Detect Anthropic-style messages endpoint."""
        request = _make_request(method="POST", path="/v1/messages")
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.0

    def test_header_detection_openai_key(self):
        """Detect OpenAI API key pattern in Authorization header."""
        request = _make_request(
            method="POST",
            path="/v1/completions",
            headers={"Authorization": "Bearer sk-proj-abc123def456"},
        )
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.0
        assert len(result.indicators) > 0

    def test_header_detection_anthropic_key(self):
        """Detect Anthropic API key pattern in x-api-key header."""
        request = _make_request(
            method="POST",
            path="/v1/messages",
            headers={"x-api-key": "sk-ant-abc123def456"},
        )
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.0

    def test_body_detection_chat_request(self):
        """Detect chat completion request from request body patterns."""
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello, world! This is a longer message to exceed the 100-byte minimum threshold for body analysis."}],
            "max_tokens": 100,
            "temperature": 0.7,
            "top_p": 0.9,
        }).encode()
        request = _make_request(
            method="POST",
            path="/some-endpoint",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.0
        assert any("body" in i.lower() for i in result.indicators)

    def test_no_match_for_non_ai_traffic(self):
        """Simple GET request to non-AI endpoint returns None."""
        request = _make_request(method="GET", path="/api/health")
        result = self.analyzer.analyze_request(request)
        assert result is None

    def test_confidence_threshold_default(self):
        """Default confidence threshold is 0.6."""
        assert self.analyzer.get_confidence_threshold() == 0.6

    def test_set_confidence_threshold(self):
        """Confidence threshold can be changed."""
        self.analyzer.set_confidence_threshold(0.8)
        assert self.analyzer.get_confidence_threshold() == 0.8

    def test_high_threshold_filters_low_confidence(self):
        """High threshold prevents low-confidence matches."""
        self.analyzer.set_confidence_threshold(0.95)

        # Minimal signal — path only, no headers or body
        request = _make_request(method="POST", path="/v1/chat/completions")
        result = self.analyzer.analyze_request(request)
        # Low confidence on path-only match should be below 0.95 threshold
        assert result is None

    def test_body_detection_large_prompt(self):
        """Large request body with AI patterns is detected."""
        body = json.dumps({
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": "A" * 500}],
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 0.95,
        }).encode()
        request = _make_request(
            method="POST",
            path="/v1/messages",
            body=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": "sk-ant-test123",
            },
        )
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.confidence > 0.5

    def test_flow_result_provider_unknown(self):
        """FlowResult reports provider as 'unknown' for flow analysis."""
        request = _make_request(method="POST", path="/v1/chat/completions")
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert result.provider == "unknown"

    def test_indicators_are_non_empty(self):
        """Matched flow indicators are populated."""
        request = _make_request(method="POST", path="/v1/chat/completions")
        result = self.analyzer.analyze_request(request)
        assert result is not None
        assert len(result.indicators) > 0

    def test_mcp_request_not_falsely_detected(self):
        """MCP-style initialization request is not falsely detected as AI API."""
        # MCP initialize request has jsonrpc but is not an AI API call
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }).encode()
        request = _make_request(
            method="POST",
            path="/mcp",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        result = self.analyzer.analyze_request(request)
        # MCP init is not an AI API call — shouldn't trigger flow analysis
        # (no model/messages/prompt/temperature in body)
        assert result is None, f"Got result: {result}"


def _make_request(
    method: str = "GET",
    path: str = "/",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
):
    """Create a mock request-like object for testing."""
    import types

    req = types.SimpleNamespace()
    req.method = method
    req.url = types.SimpleNamespace()
    req.url.path = path
    req.headers = dict(headers or {})
    req._body = body or b""
    return req
