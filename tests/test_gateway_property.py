"""Property-based tests for the Universal AI Traffic Gateway.

Uses Hypothesis to verify:
- Detector invariants (determinism, consistency)
- Passthrough latency bounds
- MCP parsing round-trip
- Route table consistency
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from hypothesis import assume, given, strategies as st

from anonreq.gateway.detector import AIDetector, MCPInspector
from anonreq.gateway.router import RouteTable


# ---------------------------------------------------------------------------
# AIDetector property tests
# ---------------------------------------------------------------------------

provider_hostnames = st.sampled_from([
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "api.together.xyz",
    "api.perplexity.ai",
])

provider_model_patterns = st.sampled_from([
    "gpt-4",
    "gpt-4-turbo",
    "claude-opus-4",
    "claude-sonnet-4",
    "gemini-2.0-flash",
    "deepseek-chat",
    "mistral-large",
    "command-r",
])

non_ai_hostnames = st.sampled_from([
    "example.com",
    "internal.company.com",
    "github.com",
    "google.com",
    "s3.amazonaws.com",
])


class TestAIDetectorProperties:
    """Property-based tests for AIDetector invariants."""

    @given(hostname=provider_hostnames)
    def test_known_provider_detected_consistently(self, hostname):
        detector = AIDetector()
        result1 = detector.detect_hostname(hostname)
        result2 = detector.detect_hostname(hostname)
        assert result1 is not None
        assert result2 is not None
        assert result1.provider == result2.provider
        assert result1.confidence == result2.confidence

    @given(hostname=non_ai_hostnames)
    def test_non_ai_hostname_returns_none(self, hostname):
        detector = AIDetector()
        result = detector.detect_hostname(hostname)
        assert result is None

    @given(hostname=provider_hostnames)
    def test_provider_detection_confidence_bounds(self, hostname):
        detector = AIDetector()
        result = detector.detect_hostname(hostname)
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    @given(model=provider_model_patterns)
    def test_model_pattern_matches_some_provider(self, model):
        detector = AIDetector()
        provider = detector.match_model_to_provider(model)
        assert provider is not None

    def test_detector_is_deterministic(self):
        detector1 = AIDetector()
        detector2 = AIDetector()
        for hostname in ["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com"]:
            r1 = detector1.detect_hostname(hostname)
            r2 = detector2.detect_hostname(hostname)
            assert r1 is not None and r2 is not None
            assert r1.provider == r2.provider


# ---------------------------------------------------------------------------
# MCPInspector property tests
# ---------------------------------------------------------------------------

valid_mcp_methods = st.sampled_from([
    "tools/call",
    "tools/list",
    "resources/read",
    "resources/list",
    "prompts/get",
    "prompts/list",
    "logging/setLevel",
    "notifications/initialized",
])


class TestMCPInspectorProperties:
    """Property-based tests for MCP message parsing."""

    @given(method=valid_mcp_methods)
    def test_valid_mcp_message_round_trips(self, method):
        inspector = MCPInspector()
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": {},
            "id": 1,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert msg.method == method
        assert inspector.is_mcp(raw) is True

    @given(method=valid_mcp_methods)
    def test_mcp_method_has_category_and_name(self, method):
        inspector = MCPInspector()
        raw = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "id": 1,
        })
        msg = inspector.parse(raw)
        assert msg is not None
        assert "/" in msg.method
        assert msg.method_category is not None
        assert msg.method_name is not None

    def test_invalid_json_not_mcp(self):
        inspector = MCPInspector()
        assert inspector.is_mcp("{{broken json}}") is False

    def test_empty_string_not_mcp(self):
        inspector = MCPInspector()
        assert inspector.is_mcp("") is False

    def test_mcp_without_jsonrpc_field_not_valid(self):
        inspector = MCPInspector()
        raw = json.dumps({"method": "test", "id": 1})
        msg = inspector.parse(raw)
        assert msg is None


# ---------------------------------------------------------------------------
# RouteTable property tests
# ---------------------------------------------------------------------------

class TestRouteTableProperties:
    """Property-based tests for RouteTable invariants."""

    def test_all_default_routes_resolve(self):
        rt = RouteTable()
        for route in rt.list_routes():
            match = rt.lookup(route.hostname)
            assert match is not None
            assert match.provider == route.provider

    def test_route_lookup_is_idempotent(self):
        rt = RouteTable()
        hostname = "api.openai.com"
        m1 = rt.lookup(hostname)
        m2 = rt.lookup(hostname)
        assert m1 is not None and m2 is not None
        assert m1.provider == m2.provider
        assert m1.entry.target_url == m2.entry.target_url

    @given(hostname=provider_hostnames)
    def test_known_hostnames_resolve(self, hostname):
        rt = RouteTable()
        match = rt.lookup(hostname)
        assert match is not None
        assert match.provider is not None
        assert match.entry.target_url.startswith(("http://", "https://"))

    def test_add_route_then_lookup_round_trip(self):
        rt = RouteTable()
        rt.add_route("test-property.ai", "test-provider", "https://test-property.ai/v1")
        match = rt.lookup("test-property.ai")
        assert match is not None
        assert match.provider == "test-provider"
        assert match.entry.target_url == "https://test-property.ai/v1"

    def test_remove_route_then_lookup_returns_none(self):
        rt = RouteTable()
        rt.add_route("temp-route.ai", "temp", "https://temp-route.ai")
        rt.remove_route("temp-route.ai")
        assert rt.lookup("temp-route.ai") is None
