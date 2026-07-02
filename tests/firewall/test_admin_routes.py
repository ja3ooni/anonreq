from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.firewall.admin import router as firewall_admin_router
from anonreq.firewall.rules import FirewallRuleLoader


@pytest.fixture
def app():
    _app = FastAPI()
    _app.include_router(firewall_admin_router)
    return _app


@pytest.fixture
def test_client(app):
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestFirewallAdminRoutes:
    @pytest.mark.asyncio
    async def test_list_rules_structure(self, test_client):
        async with test_client as client:
            resp = await client.get("/v1/admin/prompt-security/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert "rules" in body
        assert "total_rules" in body
        assert "enabled_rules" in body
        assert "version" in body
        assert isinstance(body["rules"], list)
        assert body["total_rules"] >= 14

    @pytest.mark.asyncio
    async def test_list_rules_contains_rule_fields(self, test_client):
        async with test_client as client:
            resp = await client.get("/v1/admin/prompt-security/rules")
        assert resp.status_code == 200
        body = resp.json()
        if body["rules"]:
            rule = body["rules"][0]
            assert "rule_id" in rule
            assert "category" in rule
            assert "action" in rule
            assert "enabled" in rule
            assert "severity" in rule
            assert "priority" in rule

    @pytest.mark.asyncio
    async def test_filter_by_category(self, test_client):
        async with test_client as client:
            resp = await client.get(
                "/v1/admin/prompt-security/rules?category=jailbreak"
            )
        assert resp.status_code == 200
        body = resp.json()
        for rule in body["rules"]:
            assert rule["category"] == "jailbreak"

    @pytest.mark.asyncio
    async def test_filter_by_enabled(self, test_client):
        async with test_client as client:
            resp = await client.get(
                "/v1/admin/prompt-security/rules?enabled=true"
            )
        assert resp.status_code == 200
        body = resp.json()
        for rule in body["rules"]:
            assert rule["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_single_rule(self, test_client):
        async with test_client as client:
            resp = await client.get("/v1/admin/prompt-security/rules/direct_injection_001")
        assert resp.status_code == 200
        rule = resp.json()
        assert rule["rule_id"] == "direct_injection_001"
        assert rule["category"] == "prompt_injection"
        assert "pattern" in rule

    @pytest.mark.asyncio
    async def test_get_single_rule_not_found(self, test_client):
        async with test_client as client:
            resp = await client.get("/v1/admin/prompt-security/rules/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_category_returns_422(self, test_client):
        async with test_client as client:
            resp = await client.get(
                "/v1/admin/prompt-security/rules?category=not_a_real_category"
            )
        assert resp.status_code == 422
