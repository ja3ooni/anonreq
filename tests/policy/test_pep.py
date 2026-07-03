from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision
from anonreq.policy.pep import PolicyEnforcementPoint


@pytest.fixture
def pep():
    return PolicyEnforcementPoint()


@pytest.fixture
def ctx():
    return ProcessingContext(request_id="test_req_001", tenant_id="test_tenant")


def make_decision(action: PolicyAction, matched_rule_ids: list[str] | None = None,
                  reason: str | None = None, enforcement: str | None = None) -> PolicyDecision:
    return PolicyDecision(
        action=action,
        matched_rule_ids=matched_rule_ids or [],
        decision_ts=datetime.now(timezone.utc),
        reason=reason,
        enforcement=enforcement,
    )


class TestEnforceBlock:
    @pytest.mark.asyncio
    async def test_generic_block_returns_403(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, reason="Blocked by policy")
        result = await pep.enforce(decision, ctx)
        assert result.should_forward is False
        assert result.status_code == 403
        assert "X-AnonReq-Blocked" in result.headers

    @pytest.mark.asyncio
    async def test_classification_block_returns_451(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["block_hr"], "Classification rule 'block_hr' matched level 'Highly Restricted'")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 451
        assert result.body is not None
        assert any("classification_block" in str(v) for v in result.body.values())

    @pytest.mark.asyncio
    async def test_rate_limit_block_returns_429_with_retry_after(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["rate_limit"], "RPM limit exceeded")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 429
        assert "Retry-After" in result.headers
        assert result.body is not None

    @pytest.mark.asyncio
    async def test_spend_limit_block_returns_402(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["spend_limit"], "Daily spend limit exceeded")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 402
        assert result.body is not None

    @pytest.mark.asyncio
    async def test_residency_block_returns_451(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["residency_block"], "Region cn-north-1 is blocked")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 451
        assert result.body is not None
        assert any("routing_policy_violation" in str(v) for v in result.body.values())

    @pytest.mark.asyncio
    async def test_fail_secure_returns_503(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["classification_error"], "Classification evaluation failed", enforcement="503")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_generic_error_returns_503(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["some_error"], "Internal error", enforcement="503")
        result = await pep.enforce(decision, ctx)
        assert result.status_code == 503


class TestEnforceAllow:
    @pytest.mark.asyncio
    async def test_allow_passes_through(self, pep, ctx):
        decision = make_decision(PolicyAction.ALLOW, ["all_checks_passed"])
        result = await pep.enforce(decision, ctx)
        assert result.should_forward is True
        assert result.status_code is None

    @pytest.mark.asyncio
    async def test_allow_has_processed_header(self, pep, ctx):
        decision = make_decision(PolicyAction.ALLOW, ["all_checks_passed"])
        result = await pep.enforce(decision, ctx)
        assert "X-AnonReq-Processed" in result.headers
        assert "X-AnonReq-Entity-Count" in result.headers


class TestEncodeFlagAndForward:
    @pytest.mark.asyncio
    async def test_flag_and_forward_adds_header(self, pep, ctx):
        decision = make_decision(PolicyAction.FLAG_AND_FORWARD, ["flag_conf"], "Flagged content")
        result = await pep.enforce(decision, ctx)
        assert result.should_forward is True
        assert result.status_code is None
        assert "X-AnonReq-Flagged" in result.headers

    @pytest.mark.asyncio
    async def test_flag_and_forward_also_has_transparency_headers(self, pep, ctx):
        decision = make_decision(PolicyAction.FLAG_AND_FORWARD, ["flag_conf"])
        result = await pep.enforce(decision, ctx)
        assert "X-AnonReq-Processed" in result.headers


class TestEnforceRouteLocal:
    @pytest.mark.asyncio
    async def test_route_local_returns_503(self, pep, ctx):
        decision = make_decision(PolicyAction.ROUTE_LOCAL, [], "Route to on-prem")
        result = await pep.enforce(decision, ctx)
        assert result.should_forward is False
        assert result.status_code == 503
        assert result.body is not None
        assert any("route_local" in str(v) for v in result.body.values())


class TestStructuredErrorBodies:
    @pytest.mark.asyncio
    async def test_body_has_required_fields(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["block_hr"], "Blocked by HR policy")
        result = await pep.enforce(decision, ctx)
        assert result.body is not None
        assert "reason" in result.body
        assert "decision_id" in result.body
        assert "timestamp" in result.body

    @pytest.mark.asyncio
    async def test_body_includes_decision_reason(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["rate_limit"], "RPM limit exceeded: 1001/1000")
        result = await pep.enforce(decision, ctx)
        assert result.body is not None
        assert "RPM limit exceeded" in result.body["reason"]

    @pytest.mark.asyncio
    async def test_decision_id_is_uuid_like(self, pep, ctx):
        decision = make_decision(PolicyAction.BLOCK, ["block_hr"], "Blocked")
        result = await pep.enforce(decision, ctx)
        assert result.decision_id
        assert len(result.decision_id) > 10


class TestTransparencyHeaders:
    @pytest.mark.asyncio
    async def test_add_transparency_headers_returns_all(self, pep, ctx):
        ctx.detections = [{"entity_type": "EMAIL"}]
        headers = await pep.add_transparency_headers(ctx, {})
        assert "X-AnonReq-Processed" in headers
        assert "X-AnonReq-Entity-Count" in headers
        assert headers["X-AnonReq-Entity-Count"] == "1"

    @pytest.mark.asyncio
    async def test_add_transparency_headers_zero_entity_count(self, pep, ctx):
        headers = await pep.add_transparency_headers(ctx, {})
        assert "X-AnonReq-Processed" in headers
        assert headers["X-AnonReq-Entity-Count"] == "0"

    @pytest.mark.asyncio
    async def test_add_transparency_headers_merges_existing(self, pep, ctx):
        existing = {"X-Custom": "value"}
        headers = await pep.add_transparency_headers(ctx, existing)
        assert "X-Custom" in headers
        assert "X-AnonReq-Processed" in headers
