"""Tests for agent tool permission policy: registry, evaluation, middleware.

Tests 18-01: Tool Permission Policies
- ToolPermitRegistry: per-tool permission levels (allow, allow_with_audit,
  require_human_approval, block)
- ToolPolicyEvaluator: match tool call to policy by name/pattern and tenant
- AgentMiddleware: intercept and enforce tool call governance
"""

from __future__ import annotations

import pytest
from anonreq.agent.policy import (
    ToolPermission,
    ToolPermissionLevel,
    ToolPermitRegistry,
    ToolPolicyDecision,
    ToolPolicyEvaluator,
)
from anonreq.agent.registry import ToolPermit


class TestToolPermitRegistry:
    def test_create_permit_registry_empty(self):
        registry = ToolPermitRegistry()
        assert len(registry.list_permits()) == 0

    def test_add_single_permit(self):
        registry = ToolPermitRegistry()
        permit = ToolPermit(
            tool_name="send_email",
            permission_level=ToolPermissionLevel.BLOCK,
        )
        registry.add_permit(permit)
        assert len(registry.list_permits()) == 1

    def test_add_permit_duplicate_overwrites(self):
        registry = ToolPermitRegistry()
        p1 = ToolPermit(tool_name="send_email", permission_level=ToolPermissionLevel.BLOCK)
        p2 = ToolPermit(tool_name="send_email", permission_level=ToolPermissionLevel.ALLOW)
        registry.add_permit(p1)
        registry.add_permit(p2)
        assert len(registry.list_permits()) == 1
        assert registry.evaluate("send_email", "default") == ToolPermission(ToolPermissionLevel.ALLOW, "send_email")  # noqa: E501

    def test_remove_permit(self):
        registry = ToolPermitRegistry()
        permit = ToolPermit(tool_name="send_email", permission_level=ToolPermissionLevel.BLOCK)
        registry.add_permit(permit)
        assert registry.remove_permit("send_email") is True
        assert len(registry.list_permits()) == 0

    def test_remove_nonexistent_permit_returns_false(self):
        registry = ToolPermitRegistry()
        assert registry.remove_permit("nonexistent") is False

    def test_glob_pattern_matching(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(tool_name="db_*", permission_level=ToolPermissionLevel.ALLOW_WITH_AUDIT))  # noqa: E501
        decision = registry.evaluate("db_query", "default")
        assert decision is not None
        assert decision.level == ToolPermissionLevel.ALLOW_WITH_AUDIT

    def test_exact_match_overrides_glob(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(tool_name="db_*", permission_level=ToolPermissionLevel.BLOCK))  # noqa: E501
        registry.add_permit(ToolPermit(tool_name="db_query", permission_level=ToolPermissionLevel.ALLOW))  # noqa: E501
        decision = registry.evaluate("db_query", "default")
        assert decision is not None
        assert decision.level == ToolPermissionLevel.ALLOW

    def test_default_permission_when_no_match(self):
        registry = ToolPermitRegistry()
        decision = registry.evaluate("unknown_tool", "default")
        assert decision is None

    def test_tenant_specific_permit(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(
            tool_name="send_email",
            permission_level=ToolPermissionLevel.BLOCK,
            tenant_id="tenant_a",
        ))
        decision_a = registry.evaluate("send_email", "tenant_a")
        assert decision_a is not None
        assert decision_a.level == ToolPermissionLevel.BLOCK
        decision_b = registry.evaluate("send_email", "tenant_b")
        assert decision_b is None

    def test_global_permit_falls_back_for_tenant(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(
            tool_name="send_email",
            permission_level=ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL,
        ))
        decision = registry.evaluate("send_email", "tenant_x")
        assert decision is not None
        assert decision.level == ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL

    def test_tenant_specific_overrides_global(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(
            tool_name="send_email",
            permission_level=ToolPermissionLevel.ALLOW,
        ))
        registry.add_permit(ToolPermit(
            tool_name="send_email",
            permission_level=ToolPermissionLevel.BLOCK,
            tenant_id="tenant_a",
        ))
        decision = registry.evaluate("send_email", "tenant_a")
        assert decision is not None
        assert decision.level == ToolPermissionLevel.BLOCK

    def test_permit_category_filter(self):
        registry = ToolPermitRegistry()
        registry.add_permit(ToolPermit(
            tool_name="*",
            permission_level=ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL,
            category="high_risk",
        ))
        decision = registry.evaluate("any_tool", "default", category="high_risk")
        assert decision is not None
        assert decision.level == ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL

    def test_list_permits_returns_copy(self):
        registry = ToolPermitRegistry()
        permit = ToolPermit(tool_name="test", permission_level=ToolPermissionLevel.ALLOW)
        registry.add_permit(permit)
        permits = registry.list_permits()
        permits.clear()
        assert len(registry.list_permits()) == 1


class TestToolPolicyEvaluator:
    @pytest.fixture
    def registry(self):
        r = ToolPermitRegistry()
        r.add_permit(ToolPermit("send_email", ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL))
        r.add_permit(ToolPermit("read_file", ToolPermissionLevel.ALLOW_WITH_AUDIT))
        r.add_permit(ToolPermit("delete_*", ToolPermissionLevel.BLOCK))
        r.add_permit(ToolPermit("get_weather", ToolPermissionLevel.ALLOW))
        return r

    @pytest.fixture
    def evaluator(self, registry):
        return ToolPolicyEvaluator(registry)

    def test_evaluate_openai_tool_call(self, evaluator):
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "London"}'},
            }
        ]
        decisions = evaluator.evaluate_tool_calls(tool_calls, "default")
        assert len(decisions) == 1
        assert decisions[0].level == ToolPermissionLevel.ALLOW
        assert decisions[0].tool_name == "get_weather"

    def test_evaluate_multiple_tool_calls(self, evaluator):
        tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}},  # noqa: E501
            {"id": "c2", "type": "function", "function": {"name": "send_email", "arguments": "{}"}},
        ]
        decisions = evaluator.evaluate_tool_calls(tool_calls, "default")
        assert len(decisions) == 2
        assert decisions[0].level == ToolPermissionLevel.ALLOW
        assert decisions[1].level == ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL

    def test_evaluate_anthropic_tool_use(self, evaluator):
        content = [
            {
                "type": "tool_use",
                "id": "tu_1",
                "name": "read_file",
                "input": {"path": "/data/file.txt"},
            }
        ]
        decisions = evaluator.evaluate_anthropic_content(content, "default")
        assert len(decisions) == 1
        assert decisions[0].level == ToolPermissionLevel.ALLOW_WITH_AUDIT

    def test_evaluate_mcp_tool_call(self, evaluator):
        mcp_call = {
            "method": "tools/call",
            "params": {"name": "delete_record", "arguments": {"id": 42}},
        }
        decisions = evaluator.evaluate_mcp_call(mcp_call, "default")
        assert len(decisions) == 1
        assert decisions[0].level == ToolPermissionLevel.BLOCK

    def test_unknown_tool_default_block(self, evaluator):
        tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "unknown_tool", "arguments": "{}"}},  # noqa: E501
        ]
        decisions = evaluator.evaluate_tool_calls(tool_calls, "default")
        assert len(decisions) == 1
        assert decisions[0].level == ToolPermissionLevel.BLOCK
        assert decisions[0].reason == "no matching permit"

    def test_evaluator_empty_tool_calls(self, evaluator):
        decisions = evaluator.evaluate_tool_calls([], "default")
        assert len(decisions) == 0

    def test_blocked_decision_has_correct_properties(self):
        decision = ToolPolicyDecision(
            tool_name="delete_all",
            tool_id="call_1",
            level=ToolPermissionLevel.BLOCK,
            reason="blocked by policy",
            tenant_id="default",
        )
        assert decision.tool_name == "delete_all"
        assert decision.tool_id == "call_1"
        assert decision.level == ToolPermissionLevel.BLOCK
        assert decision.reason == "blocked by policy"
        assert decision.tenant_id == "default"
        assert decision.approval_id is None


class TestAgentMiddleware:
    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        return FastAPI()

    @pytest.fixture
    def registry(self):
        r = ToolPermitRegistry()
        r.add_permit(ToolPermit("get_weather", ToolPermissionLevel.ALLOW))
        r.add_permit(ToolPermit("send_email", ToolPermissionLevel.REQUIRE_HUMAN_APPROVAL))
        r.add_permit(ToolPermit("delete_*", ToolPermissionLevel.BLOCK))
        return r

    @pytest.fixture
    def evaluator(self, registry):
        return ToolPolicyEvaluator(registry)

    @pytest.mark.asyncio
    async def test_middleware_skips_non_api_paths(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_allows_tool_call_with_permission(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        @app.post("/v1/chat/completions")
        async def chat():
            return {"choices": [{"message": {"content": "ok"}}]}

        transport = ASGITransport(app=app)
        body = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "London"}'}}  # noqa: E501
                    ],
                }
            ],
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json=body)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_blocks_denied_tool(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        @app.post("/v1/chat/completions")
        async def chat():
            return {"choices": [{"message": {"content": "ok"}}]}

        transport = ASGITransport(app=app)
        body = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "delete_all", "arguments": "{}"}}  # noqa: E501
                    ],
                }
            ],
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json=body)
        assert resp.status_code == 403
        data = resp.json()
        assert "blocked" in data.get("error", {}).get("message", "").lower()

    @pytest.mark.asyncio
    async def test_middleware_requires_approval(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        @app.post("/v1/chat/completions")
        async def chat():
            return {"choices": [{"message": {"content": "ok"}}]}

        transport = ASGITransport(app=app)
        body = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "send_email", "arguments": '{"to": "test@example.com"}'}}  # noqa: E501
                    ],
                }
            ],
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json=body)
        assert resp.status_code == 202
        data = resp.json()
        assert "approval_id" in data
        assert data["tool_name"] == "send_email"

    @pytest.mark.asyncio
    async def test_middleware_passes_request_without_tool_calls(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        @app.post("/v1/chat/completions")
        async def chat():
            return {"choices": [{"message": {"content": "hello"}}]}

        transport = ASGITransport(app=app)
        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json=body)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_skips_non_chat_routes(self, app, evaluator):
        from anonreq.middleware.agent import AgentMiddleware
        from httpx import ASGITransport, AsyncClient

        app.add_middleware(AgentMiddleware, evaluator=evaluator)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/v1/admin/config")
        assert resp.status_code == 404  # route doesn't exist, middleware passes through
