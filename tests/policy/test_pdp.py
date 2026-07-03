from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import time

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule


@pytest.fixture
def mock_policy_store():
    store = AsyncMock()
    store.enabled_rules = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_usage_limiter():
    limiter = AsyncMock()
    limiter.check_rate_limit = AsyncMock(return_value=PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc),
    ))
    return limiter


@pytest.fixture
def mock_spend_controller():
    ctrl = AsyncMock()
    ctrl.check_spend = AsyncMock(return_value=PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc),
    ))
    return ctrl


@pytest.fixture
def mock_residency_router():
    router = AsyncMock()
    router.resolve_region = AsyncMock(return_value=PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc),
    ))
    return router


@pytest.fixture
def pdp(mock_policy_store, mock_usage_limiter, mock_spend_controller, mock_residency_router):
    from anonreq.policy.pdp import PolicyDecisionPoint
    return PolicyDecisionPoint(
        policy_store=mock_policy_store,
        usage_limiter=mock_usage_limiter,
        spend_controller=mock_spend_controller,
        residency_router=mock_residency_router,
        cache_ttl=5,
    )


class TestEvaluateClassification:
    @pytest.mark.asyncio
    async def test_returns_block_for_highly_restricted(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="block_hr", action=PolicyAction.BLOCK, priority=100,
                       conditions={"classification_level": "Highly Restricted"}),
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        decision = await pdp.evaluate_classification("test_tenant", {"classification_level": "Highly Restricted"})
        assert decision.action == PolicyAction.BLOCK
        assert "block_hr" in decision.matched_rule_ids

    @pytest.mark.asyncio
    async def test_returns_allow_for_internal_with_no_matching_rule(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="block_hr", action=PolicyAction.BLOCK, priority=100,
                       conditions={"classification_level": "Highly Restricted"}),
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        decision = await pdp.evaluate_classification("test_tenant", {"classification_level": "Internal"})
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_allow_with_empty_classification_result(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="block_hr", action=PolicyAction.BLOCK, priority=100,
                       conditions={"classification_level": "Highly Restricted"}),
        ]
        decision = await pdp.evaluate_classification("test_tenant", None)
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_allow_when_no_rules(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = []
        decision = await pdp.evaluate_classification("test_tenant", {"classification_level": "Highly Restricted"})
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_block_on_store_error(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.side_effect = Exception("Redis unavailable")
        decision = await pdp.evaluate_classification("test_tenant", {"classification_level": "Highly Restricted"})
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"


class TestEvaluateRateLimit:
    @pytest.mark.asyncio
    async def test_returns_block_when_usage_limiter_denies(self, pdp, mock_usage_limiter):
        mock_usage_limiter.check_rate_limit.return_value = PolicyDecision(
            action=PolicyAction.BLOCK, matched_rule_ids=["rate_limit"],
            decision_ts=datetime.now(timezone.utc), reason="RPM limit exceeded",
        )
        decision = await pdp.evaluate_rate_limit("test_tenant")
        assert decision.action == PolicyAction.BLOCK
        assert "rate_limit" in decision.matched_rule_ids

    @pytest.mark.asyncio
    async def test_returns_allow_when_rate_ok(self, pdp, mock_usage_limiter):
        mock_usage_limiter.check_rate_limit.return_value = PolicyDecision(
            action=PolicyAction.ALLOW, matched_rule_ids=["rate_limit"],
            decision_ts=datetime.now(timezone.utc),
        )
        decision = await pdp.evaluate_rate_limit("test_tenant")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_block_on_limiter_error(self, pdp, mock_usage_limiter):
        mock_usage_limiter.check_rate_limit.side_effect = Exception("Redis error")
        decision = await pdp.evaluate_rate_limit("test_tenant")
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"


class TestEvaluateSpend:
    @pytest.mark.asyncio
    async def test_returns_block_when_spend_exceeded(self, pdp, mock_spend_controller):
        mock_spend_controller.check_spend.return_value = PolicyDecision(
            action=PolicyAction.BLOCK, matched_rule_ids=["spend_limit"],
            decision_ts=datetime.now(timezone.utc), reason="Daily spend limit exceeded",
        )
        decision = await pdp.evaluate_spend("test_tenant")
        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_returns_allow_when_spend_ok(self, pdp, mock_spend_controller):
        mock_spend_controller.check_spend.return_value = PolicyDecision(
            action=PolicyAction.ALLOW, matched_rule_ids=["spend_limit"],
            decision_ts=datetime.now(timezone.utc),
        )
        decision = await pdp.evaluate_spend("test_tenant")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_block_on_controller_error(self, pdp, mock_spend_controller):
        mock_spend_controller.check_spend.side_effect = Exception("Redis error")
        decision = await pdp.evaluate_spend("test_tenant")
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"


class TestEvaluateResidency:
    @pytest.mark.asyncio
    async def test_returns_block_when_region_blocked(self, pdp, mock_residency_router):
        mock_residency_router.resolve_region.return_value = PolicyDecision(
            action=PolicyAction.BLOCK, matched_rule_ids=["residency_block"],
            decision_ts=datetime.now(timezone.utc), reason="Region cn-north-1 is blocked",
        )
        decision = await pdp.evaluate_residency("test_tenant", "openai", "cn-north-1")
        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_returns_allow_when_region_allowed(self, pdp, mock_residency_router):
        mock_residency_router.resolve_region.return_value = PolicyDecision(
            action=PolicyAction.ALLOW, matched_rule_ids=["residency_match"],
            decision_ts=datetime.now(timezone.utc), reason="Region us-east-1 is allowed",
        )
        decision = await pdp.evaluate_residency("test_tenant", "openai", "us-east-1")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_returns_block_on_router_error(self, pdp, mock_residency_router):
        mock_residency_router.resolve_region.side_effect = Exception("Router error")
        decision = await pdp.evaluate_residency("test_tenant", "openai", "cn-north-1")
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"


class TestEvaluateAll:
    @pytest.mark.asyncio
    async def test_returns_allow_when_all_checks_pass(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        ctx.classification_result = {"classification_level": "Internal"}
        ctx.model = "gpt-4"
        ctx.provider = "openai"
        decision = await pdp.evaluate_all(ctx)
        assert decision.action == PolicyAction.ALLOW
        assert decision.matched_rule_ids == ["all_checks_passed"]

    @pytest.mark.asyncio
    async def test_fail_fast_classification_block_shortcircuits(self, pdp, mock_policy_store, mock_usage_limiter):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="block_hr", action=PolicyAction.BLOCK, priority=100,
                       conditions={"classification_level": "Highly Restricted"}),
        ]
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        ctx.classification_result = {"classification_level": "Highly Restricted"}
        decision = await pdp.evaluate_all(ctx)
        assert decision.action == PolicyAction.BLOCK
        mock_usage_limiter.check_rate_limit.assert_not_called()

    @pytest.mark.asyncio
    async def test_fail_fast_rate_limit_block_shortcircuits(self, pdp, mock_policy_store, mock_spend_controller):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        from anonreq.policy.pdp import PolicyDecisionPoint
        limiter = AsyncMock()
        limiter.check_rate_limit = AsyncMock(return_value=PolicyDecision(
            action=PolicyAction.BLOCK, matched_rule_ids=["rate_limit"],
            decision_ts=datetime.now(timezone.utc), reason="RPM exceeded",
        ))
        spend_ctrl = AsyncMock()
        pdp_rate = PolicyDecisionPoint(
            policy_store=mock_policy_store,
            usage_limiter=limiter,
            spend_controller=spend_ctrl,
            residency_router=pdp._residency_router,
            cache_ttl=5,
        )
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        ctx.classification_result = {"classification_level": "Internal"}
        decision = await pdp_rate.evaluate_all(ctx)
        assert decision.action == PolicyAction.BLOCK
        spend_ctrl.check_spend.assert_not_called()

    @pytest.mark.asyncio
    async def test_caches_decision_within_ttl(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        ctx.classification_result = {"classification_level": "Internal"}
        ctx.model = "gpt-4"
        await pdp.evaluate_all(ctx)
        await pdp.evaluate_all(ctx)
        assert mock_policy_store.enabled_rules.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_bypass_after_ttl(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        ctx.classification_result = {"classification_level": "Internal"}
        ctx.model = "gpt-4"
        with patch("time.monotonic", side_effect=[100.0, 106.0, 106.0]):
            await pdp.evaluate_all(ctx)
            await pdp.evaluate_all(ctx)
        assert mock_policy_store.enabled_rules.call_count == 2

    @pytest.mark.asyncio
    async def test_fail_closed_on_store_error(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.side_effect = Exception("Cache unavailable")
        ctx = ProcessingContext(request_id="test", tenant_id="test_tenant")
        decision = await pdp.evaluate_all(ctx)
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"

    @pytest.mark.asyncio
    async def test_different_contexts_get_different_cache_entries(self, pdp, mock_policy_store):
        mock_policy_store.enabled_rules.return_value = [
            PolicyRule(rule_id="allow_default", action=PolicyAction.ALLOW, priority=0),
        ]
        ctx_a = ProcessingContext(request_id="a", tenant_id="tenant_a")
        ctx_a.classification_result = {"classification_level": "Internal"}
        ctx_a.model = "gpt-4"
        ctx_b = ProcessingContext(request_id="b", tenant_id="tenant_b")
        ctx_b.classification_result = {"classification_level": "Internal"}
        ctx_b.model = "gpt-4"
        await pdp.evaluate_all(ctx_a)
        await pdp.evaluate_all(ctx_b)
        assert mock_policy_store.enabled_rules.call_count == 2
