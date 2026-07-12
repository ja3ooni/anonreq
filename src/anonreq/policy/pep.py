from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision


@dataclass
class PolicyEnforcementResult:
    action: PolicyAction
    status_code: int | None
    headers: dict[str, str] = field(default_factory=dict)
    body: dict | None = None
    should_forward: bool = False
    decision_id: str = ""


class PolicyEnforcementPoint:
    async def enforce(
        self, decision: PolicyDecision, ctx: ProcessingContext,
    ) -> PolicyEnforcementResult:
        decision_id = uuid4().hex[:16]
        now = datetime.now(UTC).isoformat()

        if decision.action == PolicyAction.ALLOW:
            entity_count = str(len(ctx.detections)) if ctx.detections else "0"
            headers = {
                "X-AnonReq-Processed": "true" if ctx.transformed_request else "false",
                "X-AnonReq-Entity-Count": entity_count,
            }
            return PolicyEnforcementResult(
                action=PolicyAction.ALLOW,
                status_code=None,
                headers=headers,
                body=None,
                should_forward=True,
                decision_id=decision_id,
            )

        if decision.action == PolicyAction.FLAG_AND_FORWARD:
            entity_count = str(len(ctx.detections)) if ctx.detections else "0"
            headers = {
                "X-AnonReq-Flagged": "true",
                "X-AnonReq-Processed": "true" if ctx.transformed_request else "false",
                "X-AnonReq-Entity-Count": entity_count,
            }
            return PolicyEnforcementResult(
                action=PolicyAction.FLAG_AND_FORWARD,
                status_code=None,
                headers=headers,
                body=None,
                should_forward=True,
                decision_id=decision_id,
            )

        if decision.action == PolicyAction.ROUTE_LOCAL:
            body = {
                "reason": "route_local",
                "decision_id": decision_id,
                "timestamp": now,
                "detail": "Request must be routed to local inference endpoint",
            }
            return PolicyEnforcementResult(
                action=PolicyAction.ROUTE_LOCAL,
                status_code=503,
                headers={"X-AnonReq-Blocked": "true"},
                body=body,
                should_forward=False,
                decision_id=decision_id,
            )

        return self._handle_block(decision, decision_id, now, ctx)

    def _determine_block_type(
        self, decision: PolicyDecision,
    ) -> tuple[int, str, dict]:
        for rid in decision.matched_rule_ids:
            if "rate_limit" in rid:
                return 429, "rate_limit_exceeded", {
                    "Retry-After": "60",
                }

        if decision.enforcement == "503" or any(
            "error" in rid for rid in decision.matched_rule_ids
        ):
            return 503, "fail_secure", {}

        reason = (decision.reason or "").lower()

        if "spend" in reason or any("spend" in rid for rid in decision.matched_rule_ids):
            return 402, "spend_limit_exceeded", {}

        if "residency" in reason or any("residency" in rid for rid in decision.matched_rule_ids):
            return 451, "routing_policy_violation", {}

        if "classification" in reason or any(
            rid for rid in decision.matched_rule_ids
            if "classification" in rid or rid.startswith("block_")
        ):
            return 451, "classification_block", {}

        return 403, "blocked", {}

    def _handle_block(
        self, decision: PolicyDecision, decision_id: str, now: str,
        _ctx: ProcessingContext,
    ) -> PolicyEnforcementResult:
        status_code, block_type, extra_headers = self._determine_block_type(decision)

        body: dict = {
            "reason": decision.reason or "Request blocked by policy",
            "decision_id": decision_id,
            "timestamp": now,
        }

        if block_type == "rate_limit_exceeded":
            body["error_type"] = "rate_limit_exceeded"
        elif block_type == "spend_limit_exceeded":
            body["error_type"] = "spend_limit_exceeded"
        elif block_type == "classification_block":
            body["error_type"] = "classification_block"
        elif block_type == "routing_policy_violation":
            body["error_type"] = "routing_policy_violation"
        elif block_type == "fail_secure":
            body["error_type"] = "fail_secure"

        headers = {"X-AnonReq-Blocked": "true", **extra_headers}

        return PolicyEnforcementResult(
            action=PolicyAction.BLOCK,
            status_code=status_code,
            headers=headers,
            body=body,
            should_forward=False,
            decision_id=decision_id,
        )

    async def add_transparency_headers(
        self, ctx: ProcessingContext, existing_headers: dict[str, str],
    ) -> dict[str, str]:
        entity_count = str(len(ctx.detections)) if ctx.detections else "0"
        headers = dict(existing_headers)
        headers.setdefault("X-AnonReq-Processed", "true" if ctx.transformed_request else "false")
        headers.setdefault("X-AnonReq-Entity-Count", entity_count)
        return headers
