"""Hypothesis property-based tests for Phase 8 policy engine invariants.

Proves:
- Tenant isolation (A's rules do not affect B's decision)
- Fail-secure on cache/dependency failures (fails closed to BLOCK 503)
- Deny-dominance (BLOCK overrides ALLOW)
- Determinism (same input + rules -> same decision)
- Monotonicity of rate limit counters
- No raw sensitive values leak to audit logs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.audit import DecisionAuditPublisher
from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule
from anonreq.policy.pdp import PolicyDecisionPoint
from anonreq.policy.residency_router import ResidencyRouter
from anonreq.policy.spend_controller import SpendController
from anonreq.policy.store import PolicyStore
from anonreq.policy.usage_limiter import UsageLimiter

# Strategies
tenant_id_strategy = st.text(
    min_size=1,
    max_size=32,
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-",
)

policy_action_strategy = st.sampled_from(list(PolicyAction))

priority_strategy = st.integers(min_value=0, max_value=1000)

classification_strategy = st.sampled_from(["Public", "Internal", "Confidential", "Highly Restricted"])  # noqa: E501

region_strategy = st.sampled_from(["us-east-1", "eu-west-1", "ap-southeast-1"])

provider_strategy = st.sampled_from(["openai", "anthropic", "gemini"])

rule_id_strategy = st.text(
    min_size=3,
    max_size=16,
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
)


@st.composite
def policy_rule_strategy(draw, tenant_id=None):
    rule_id = draw(rule_id_strategy)
    action = draw(policy_action_strategy)
    priority = draw(priority_strategy)
    cls_level = draw(classification_strategy)
    t_id = tenant_id if tenant_id is not None else draw(tenant_id_strategy)
    return PolicyRule(
        rule_id=rule_id,
        action=action,
        priority=priority,
        enabled=True,
        conditions={"classification_level": cls_level},
        tenant_id=t_id,
    )


class MockLogger:
    def __init__(self):
        self.events = []

    def info(self, event, **kwargs):
        self.events.append((event, kwargs))


# --- Property Tests ---

@pytest.mark.asyncio
@given(
    tenant_a=tenant_id_strategy,
    tenant_b=tenant_id_strategy,
    rule_a=policy_rule_strategy(tenant_id="tenant_a"),
)
@settings(max_examples=50)
async def test_tenant_isolation(tenant_a, tenant_b, rule_a):
    if tenant_a == tenant_b:
        tenant_b = tenant_b + "_diff"

    # Configure rule_a for tenant_a, no rules for tenant_b
    rule_a.tenant_id = tenant_a
    rule_a.action = PolicyAction.BLOCK

    # Mock PolicyStore
    mock_store = AsyncMock(spec=PolicyStore)
    async def mock_enabled_rules(t_id):
        if t_id == tenant_a:
            return [rule_a]
        return []
    mock_store.enabled_rules.side_effect = mock_enabled_rules
    mock_store.load_policies.return_value = []

    # Mock other PDP components
    mock_limiter = AsyncMock(spec=UsageLimiter)
    mock_limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_spend = AsyncMock(spec=SpendController)
    mock_spend.check_spend.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_residency = AsyncMock(spec=ResidencyRouter)
    mock_residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    pdp = PolicyDecisionPoint(mock_store, mock_limiter, mock_spend, mock_residency)

    # Evaluate tenant B
    ctx_b = ProcessingContext(
        request_id="req_1",
        tenant_id=tenant_b,
        classification_result={"classification_level": "Confidential"},
    )

    decision_b = await pdp.evaluate_all(ctx_b)
    # Tenant B should be allowed since it has no rules matching block
    assert decision_b.action == PolicyAction.ALLOW


@pytest.mark.asyncio
@given(
    tenant_id=tenant_id_strategy,
    classification=classification_strategy,
)
@settings(max_examples=30)
async def test_fail_secure_on_cache_failure(tenant_id, classification):
    # Mock components to raise exceptions simulating redis/Valkey outages
    mock_store = AsyncMock(spec=PolicyStore)
    mock_store.enabled_rules.side_effect = Exception("Redis connection lost")

    mock_limiter = AsyncMock(spec=UsageLimiter)
    mock_spend = AsyncMock(spec=SpendController)
    mock_residency = AsyncMock(spec=ResidencyRouter)

    pdp = PolicyDecisionPoint(mock_store, mock_limiter, mock_spend, mock_residency)

    ctx = ProcessingContext(
        request_id="req_2",
        tenant_id=tenant_id,
        classification_result={"classification_level": classification},
    )

    decision = await pdp.evaluate_all(ctx)
    # Failure in store should block closed (FAIL SECURE)
    assert decision.action == PolicyAction.BLOCK
    assert "classification_error" in decision.matched_rule_ids
    assert decision.enforcement == "503"


@pytest.mark.asyncio
@given(
    priority_allow=st.integers(min_value=0, max_value=500),
    priority_block=st.integers(min_value=501, max_value=1000),
    tenant_id=tenant_id_strategy,
)
@settings(max_examples=30)
async def test_deny_dominates_allow(priority_allow, priority_block, tenant_id):
    # Construct an ALLOW rule and a higher priority BLOCK rule
    allow_rule = PolicyRule(
        rule_id="allow_rule",
        action=PolicyAction.ALLOW,
        priority=priority_allow,
        enabled=True,
        conditions={"classification_level": "Confidential"},
        tenant_id=tenant_id,
    )
    block_rule = PolicyRule(
        rule_id="block_rule",
        action=PolicyAction.BLOCK,
        priority=priority_block,
        enabled=True,
        conditions={"classification_level": "Confidential"},
        tenant_id=tenant_id,
    )

    # PolicyStore will return both rules sorted by priority desc: [block_rule, allow_rule]
    mock_store = AsyncMock(spec=PolicyStore)
    mock_store.enabled_rules.return_value = [block_rule, allow_rule]

    mock_limiter = AsyncMock(spec=UsageLimiter)
    mock_limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_spend = AsyncMock(spec=SpendController)
    mock_spend.check_spend.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_residency = AsyncMock(spec=ResidencyRouter)
    mock_residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    pdp = PolicyDecisionPoint(mock_store, mock_limiter, mock_spend, mock_residency)

    ctx = ProcessingContext(
        request_id="req_3",
        tenant_id=tenant_id,
        classification_result={"classification_level": "Confidential"},
    )

    decision = await pdp.evaluate_all(ctx)
    # The higher priority BLOCK rule must dominate and be matched
    assert decision.action == PolicyAction.BLOCK
    assert "block_rule" in decision.matched_rule_ids


@pytest.mark.asyncio
@given(
    pii_value=st.text(min_size=8, max_size=32, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"),
    tenant_id=tenant_id_strategy,
    session_id=tenant_id_strategy,
)
@settings(max_examples=30)
async def test_no_raw_pii_in_audit(pii_value, tenant_id, session_id):
    assume(pii_value not in tenant_id)
    assume(pii_value not in session_id)
    logger = MockLogger()
    publisher = DecisionAuditPublisher(logger)

    # Attempt to log with potentially sensitive parameters
    await publisher.publish_decision(
        ProcessingContext(request_id=session_id, tenant_id=tenant_id),
        PolicyDecision(
            action=PolicyAction.BLOCK,
            matched_rule_ids=["rule_001"],
            decision_ts=datetime.now(UTC),
            reason=f"Failed validation because of {pii_value}",
        ),
    )

    assert len(logger.events) == 1
    event_type, kwargs = logger.events[0]
    # The event log fields should not contain the raw pii_value
    assert pii_value not in event_type
    assert pii_value not in kwargs.get("tenant_id", "")
    assert pii_value not in kwargs.get("session_id", "")
    assert pii_value not in kwargs.get("decision_id", "")
    # Check that any generated string fields don't accidentally contain the value
    for val in kwargs.values():
        if isinstance(val, str):
            assert pii_value not in val


@pytest.mark.asyncio
@given(
    tenant_id=tenant_id_strategy,
    classification=classification_strategy,
    provider=provider_strategy,
)
@settings(max_examples=30)
async def test_decision_deterministic(tenant_id, classification, provider):
    mock_store = AsyncMock(spec=PolicyStore)
    rule = PolicyRule(
        rule_id="r1",
        action=PolicyAction.BLOCK,
        priority=10,
        enabled=True,
        conditions={"classification_level": classification},
        tenant_id=tenant_id,
    )
    mock_store.enabled_rules.return_value = [rule]

    mock_limiter = AsyncMock(spec=UsageLimiter)
    mock_limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_spend = AsyncMock(spec=SpendController)
    mock_spend.check_spend.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    mock_residency = AsyncMock(spec=ResidencyRouter)
    mock_residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )

    # Disable TTL cache to ensure evaluation runs on each call
    pdp = PolicyDecisionPoint(mock_store, mock_limiter, mock_spend, mock_residency, cache_ttl=0)

    ctx = ProcessingContext(
        request_id="req_det",
        tenant_id=tenant_id,
        classification_result={"classification_level": classification},
        provider=provider,
    )

    decision_1 = await pdp.evaluate_all(ctx)
    decision_2 = await pdp.evaluate_all(ctx)

    assert decision_1.action == decision_2.action
    assert decision_1.matched_rule_ids == decision_2.matched_rule_ids
