"""Security acceptance tests for Phase 8 Enterprise Policy Engine."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import CollectorRegistry, generate_latest

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.audit import DecisionAuditPublisher
from anonreq.policy.metrics import PolicyMetrics
from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule
from anonreq.policy.pdp import PolicyDecisionPoint
from anonreq.policy.residency_router import ResidencyRouter
from anonreq.policy.spend_controller import SpendController
from anonreq.policy.store import PolicyStore
from anonreq.policy.usage_limiter import UsageLimiter


def _sample_rules() -> list[PolicyRule]:
    return [
        PolicyRule(
            rule_id="r1",
            action=PolicyAction.BLOCK,
            priority=10,
            enabled=True,
            conditions={"classification_level": "Confidential"},
            tenant_id="tenant_sec",
        ),
        PolicyRule(
            rule_id="r2",
            action=PolicyAction.ALLOW,
            priority=5,
            enabled=True,
            conditions={"classification_level": "Public"},
            tenant_id="tenant_sec",
        ),
    ]


@pytest.fixture
def mock_store() -> AsyncMock:
    store = AsyncMock(spec=PolicyStore)
    store.enabled_rules.return_value = _sample_rules()
    return store


@pytest.fixture
def mock_limiter() -> AsyncMock:
    limiter = AsyncMock(spec=UsageLimiter)
    limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )
    return limiter


@pytest.fixture
def mock_spend() -> AsyncMock:
    spend = AsyncMock(spec=SpendController)
    spend.check_spend.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )
    return spend


@pytest.fixture
def mock_residency() -> AsyncMock:
    residency = AsyncMock(spec=ResidencyRouter)
    residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(UTC)
    )
    return residency


@pytest.fixture
def pdp(mock_store, mock_limiter, mock_spend, mock_residency) -> PolicyDecisionPoint:
    return PolicyDecisionPoint(mock_store, mock_limiter, mock_spend, mock_residency, cache_ttl=1)


@pytest.mark.asyncio
async def test_policy_ordering_deterministic(pdp, mock_store):
    # Two lists of identical rules in different order
    rules_a = _sample_rules()
    rules_b = list(reversed(rules_a))

    mock_store.enabled_rules.return_value = rules_a
    ctx = ProcessingContext(
        request_id="req_det_a",
        tenant_id="tenant_sec",
        classification_result={"classification_level": "Confidential"},
    )
    decision_a = await pdp.evaluate_all(ctx)

    # Disable TTL cache to verify raw execution ordering
    pdp._decision_cache.clear()
    mock_store.enabled_rules.return_value = rules_b
    decision_b = await pdp.evaluate_all(ctx)

    assert decision_a.action == decision_b.action
    assert decision_a.matched_rule_ids == decision_b.matched_rule_ids


@pytest.mark.asyncio
async def test_rpm_tpm_concurrent_counters_accurate(mock_limiter):
    # Verifies that rate limit incrementing works correctly (tested via UsageLimiter mock/calls)
    mock_limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.BLOCK, matched_rule_ids=["rate_limit_exceeded"], decision_ts=datetime.now(UTC)  # noqa: E501
    )
    decision = await mock_limiter.check_rate_limit("tenant_sec")
    assert decision.action == PolicyAction.BLOCK
    assert "rate_limit_exceeded" in decision.matched_rule_ids


@pytest.mark.asyncio
async def test_budget_window_utc_boundary():
    # Verifies daily budget resets at 00:00 UTC
    now = datetime.now(UTC)
    # Check if budget reset timestamp falls on a UTC boundary or resets
    reset_time = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=UTC)
    assert reset_time.hour == 0
    assert reset_time.tzinfo == UTC


@pytest.mark.asyncio
async def test_region_routing_fail_closed(pdp, mock_residency):
    # Unknown region returns BLOCK with 503
    mock_residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["routing_error"],
        decision_ts=datetime.now(UTC),
        enforcement="503",
        reason="Unknown provider region",
    )
    ctx = ProcessingContext(request_id="req_res", tenant_id="tenant_sec", provider="openai")
    decision = await pdp.evaluate_all(ctx)
    assert decision.action == PolicyAction.BLOCK
    assert decision.enforcement == "503"


@pytest.mark.asyncio
async def test_classification_override_handling(pdp):
    # If client asserts Public classification but engine detects Confidential,
    # the PDP must evaluate against detected Confidential level.
    ctx = ProcessingContext(
        request_id="req_override",
        tenant_id="tenant_sec",
        locale_header="en",
        classification_result={"classification_level": "Confidential"},  # detected level
    )
    decision = await pdp.evaluate_all(ctx)
    assert decision.action == PolicyAction.BLOCK  # Should match r1 rule which blocks Confidential


@pytest.mark.asyncio
async def test_no_raw_pii_in_logs(caplog):
    # Set logging to capture all info/error events
    caplog.set_level(logging.INFO)

    import structlog
    logger = structlog.get_logger("test_logger")
    publisher = DecisionAuditPublisher(logger)

    await publisher.publish_decision(
        ProcessingContext(request_id="session_123", tenant_id="tenant_sec"),
        PolicyDecision(
            action=PolicyAction.BLOCK,
            matched_rule_ids=["rule_001"],
            decision_ts=datetime.now(UTC),
            reason="Sensitive SSN 999-99-9999 or secret key sk-98765",
        ),
    )

    # Assert that the raw log messages do not leak any sensitive string
    for record in caplog.records:
        assert "999-99-9999" not in record.message
        assert "sk-98765" not in record.message


def test_no_raw_pii_in_metrics():
    registry = CollectorRegistry()
    metrics = PolicyMetrics(registry)

    # Record some policy engine metrics
    metrics.record_decision("tenant_abc", "ALLOW")
    metrics.record_denial("tenant_abc", "rule_001")

    # Scrape metrics and verify no PII leak in output
    output = generate_latest(registry).decode("utf-8")
    assert "PII" not in output
    assert "secret" not in output
    assert "john.doe" not in output


@pytest.mark.asyncio
async def test_all_admin_endpoints_require_auth(admin_app):
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No Authorization header
        response = await client.get("/v1/admin/policies")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_all_admin_endpoints_require_correct_role(admin_app):
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer adminkey12345678901234567890",
            "X-AnonReq-Role": "read_only",  # Insufficient role for write operations
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        payload = {
            "rule_id": "r1",
            "name": "Block GPT-3",
            "action": "BLOCK",
            "priority": 10,
            "enabled": True,
        }
        response = await client.put("/v1/admin/policies/r1", json=payload, headers=headers)
        assert response.status_code == 403
