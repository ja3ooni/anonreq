"""Tests for ResidencyRouter."""

from __future__ import annotations

import pytest

from anonreq.policy.models import PolicyAction, ResidencyRule
from anonreq.policy.residency_router import ResidencyRouter


@pytest.fixture
def router():
    rules = {
        "tenant_acme": ResidencyRule(
            allowed_regions=["us-east-1", "eu-west-1"],
            blocked_regions=["cn-north-1"],
            fallback_action=PolicyAction.BLOCK,
            required=False,
        ),
        "tenant_gov": ResidencyRule(
            allowed_regions=["us-gov-west-1"],
            blocked_regions=[],
            fallback_action=PolicyAction.ROUTE_LOCAL,
            required=True,
        ),
    }
    return ResidencyRouter(rules)


class TestResidencyRouter:
    @pytest.mark.asyncio
    async def test_resolve_region_returns_allow_when_in_allowed(self, router):
        decision = await router.resolve_region("tenant_acme", "us-east-1", "openai")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_resolve_region_returns_allow_for_any_allowed_region(self, router):
        decision = await router.resolve_region("tenant_acme", "eu-west-1", "anthropic")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_resolve_region_blocks_blocked_region(self, router):
        decision = await router.resolve_region("tenant_acme", "cn-north-1", "openai")
        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_resolve_region_returns_fallback_for_unknown_region(self, router):
        decision = await router.resolve_region("tenant_acme", "ap-southeast-1", "openai")
        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_resolve_region_returns_route_local_for_required_regions(self, router):
        decision = await router.resolve_region("tenant_gov", "us-gov-west-1", "openai")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_resolve_region_returns_route_local_fallback(self, router):
        decision = await router.resolve_region("tenant_gov", "eu-west-1", "openai")
        assert decision.action == PolicyAction.ROUTE_LOCAL

    @pytest.mark.asyncio
    async def test_resolve_region_allow_for_no_tenant_rules(self, router):
        decision = await router.resolve_region("tenant_nonexistent", "us-east-1", "openai")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_resolve_region_blocks_when_required_region_not_used(self, router):
        decision = await router.resolve_region("tenant_gov", "us-east-1", "openai")
        assert decision.action == PolicyAction.ROUTE_LOCAL
