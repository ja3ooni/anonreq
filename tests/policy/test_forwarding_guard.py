from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision


@pytest.fixture
def valid_ctx():
    ctx = ProcessingContext(request_id="test_req", tenant_id="test_tenant")
    ctx.policy_decision = PolicyDecision(
        action=PolicyAction.ALLOW,
        matched_rule_ids=["all_checks_passed"],
        decision_ts=datetime.now(timezone.utc),
        ttl_seconds=60,
    )
    ctx.transformed_request = {"model": "gpt-4", "messages": []}
    return ctx


class TestForwardingGuard:
    @pytest.mark.asyncio
    async def test_passes_valid_request(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.ALLOW
        assert verdict.http_status == 200

    @pytest.mark.asyncio
    async def test_blocks_when_no_policy_decision(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = None
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK
        assert verdict.http_status == 503
        assert "no policy decision" in verdict.reason.lower()

    @pytest.mark.asyncio
    async def test_blocks_when_policy_action_is_block(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = PolicyDecision(
            action=PolicyAction.BLOCK, matched_rule_ids=["block_hr"],
            decision_ts=datetime.now(timezone.utc), ttl_seconds=60,
        )
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK
        assert verdict.http_status == 403

    @pytest.mark.asyncio
    async def test_blocks_when_transformed_request_is_none(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.transformed_request = None
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK
        assert "transformed_request" in verdict.reason.lower()

    @pytest.mark.asyncio
    async def test_blocks_when_decision_ttl_expired(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = PolicyDecision(
            action=PolicyAction.ALLOW, matched_rule_ids=["all_checks_passed"],
            decision_ts=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ttl_seconds=1,
        )
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK
        assert "ttl" in verdict.reason.lower() or "expired" in verdict.reason.lower()

    @pytest.mark.asyncio
    async def test_blocks_flag_and_forward_when_no_transformed_request(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = PolicyDecision(
            action=PolicyAction.FLAG_AND_FORWARD, matched_rule_ids=["flag_conf"],
            decision_ts=datetime.now(timezone.utc), ttl_seconds=60,
        )
        valid_ctx.transformed_request = None
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_fail_closed_on_internal_error(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = PolicyDecision(
            action=PolicyAction.ALLOW, matched_rule_ids=[],
            decision_ts=datetime.now(timezone.utc), ttl_seconds=60,
        )
        valid_ctx.transformed_request = None
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_verdict_has_error_body_when_blocked(self, valid_ctx):
        from anonreq.policy.forwarding_guard import ForwardingGuard
        guard = ForwardingGuard()
        valid_ctx.policy_decision = None
        verdict = await guard.validate(valid_ctx)
        assert verdict.action == PolicyAction.BLOCK
        assert verdict.error_body is not None
        assert "reason" in verdict.error_body
