from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction

logger = get_logger("anonreq.policy.forwarding_guard")


@dataclass
class ForwardingVerdict:
    action: PolicyAction
    reason: str | None
    http_status: int
    error_body: dict[str, Any] | None = None
    ctx: ProcessingContext | None = None


class ForwardingGuard:
    async def validate(self, ctx: ProcessingContext) -> ForwardingVerdict:
        try:
            if ctx.policy_decision is None:
                logger.warning("forwarding_guard.no_decision", request_id=ctx.request_id)
                return self._block("no policy decision", 503)

            action = ctx.policy_decision.action
            if action not in (PolicyAction.ALLOW, PolicyAction.FLAG_AND_FORWARD):
                reason = ctx.policy_decision.reason or f"Policy action is {action.value}"
                http_status = 403 if action == PolicyAction.BLOCK else 503
                return self._block(reason, http_status)

            if ctx.transformed_request is None:
                logger.warning(
                    "forwarding_guard.no_transformed_request",
                    request_id=ctx.request_id,
                    action=action.value,
                )
                return self._block("transformed_request is None", 503)

            decision_ts = ctx.policy_decision.decision_ts
            ttl = ctx.policy_decision.ttl_seconds
            elapsed = (datetime.now(UTC) - decision_ts).total_seconds()
            if elapsed > ttl:
                logger.warning(
                    "forwarding_guard.ttl_expired",
                    request_id=ctx.request_id,
                    elapsed_seconds=elapsed,
                    ttl_seconds=ttl,
                )
                return self._block("policy decision TTL expired", 503)

            logger.info(
                "forwarding_guard.passed",
                request_id=ctx.request_id,
                action=action.value,
            )
            return ForwardingVerdict(
                action=PolicyAction.ALLOW,
                reason=None,
                http_status=200,
                ctx=ctx,
            )

        except Exception as exc:
            logger.error("forwarding_guard.error", error=str(exc), request_id=ctx.request_id)
            return self._block("internal guard error", 503)

    def _block(self, reason: str, http_status: int) -> ForwardingVerdict:
        return ForwardingVerdict(
            action=PolicyAction.BLOCK,
            reason=reason,
            http_status=http_status,
            error_body={"reason": reason},
        )
