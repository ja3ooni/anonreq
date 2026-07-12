"""Policy Decision Audit Publisher.

Emits structured audit events for policy engine actions (decisions, blocks, limits).
All events are metadata-only and strictly filtered against a field allowlist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.metrics import register_policy_metrics
from anonreq.policy.models import PolicyAction, PolicyDecision

ALLOWED_FIELDS: frozenset[str] = frozenset({
    "event_type",
    "timestamp",
    "tenant_id",
    "session_id",
    "actor_id",
    "decision_id",
    "action",
    "matched_rule_ids",
    "limit_type",
    "current_value",
    "limit",
    "budget_type",
    "current_spend",
    "budget_limit",
    "currency",
    "provider",
    "region",
    "allowed_regions",
    "classification_level",
    "matched_rule_id",
    "reset_at",
})


class PolicyAuditEvent(BaseModel):
    """Pydantic model representing a structured, metadata-only policy audit event."""

    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str
    session_id: str | None = None
    actor_id: str | None = None
    decision_id: str | None = None
    action: PolicyAction | None = None
    matched_rule_ids: list[str] = []
    metadata: dict[str, Any] = {}


class DecisionAuditPublisher:
    """Publishes structured metadata-only audit events for policy decisions and limits."""

    def __init__(self, audit_logger: Any) -> None:
        """Initialize with a structured logger."""
        self._logger = audit_logger

    def _build_event(self, event_type: str, **fields: Any) -> PolicyAuditEvent:
        """Construct a PolicyAuditEvent, enforcing the metadata-only field allowlist."""
        # Filter fields against metadata allowlist
        filtered = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}

        # Coerce Decimal values to float for JSON compatibility
        for k, v in list(filtered.items()):
            if isinstance(v, Decimal):
                filtered[k] = float(v)

        timestamp = filtered.pop("timestamp", None) or datetime.now(UTC)
        tenant_id = filtered.pop("tenant_id", "default")
        session_id = filtered.pop("session_id", None)
        actor_id = filtered.pop("actor_id", None)
        decision_id = filtered.pop("decision_id", None)
        action = filtered.pop("action", None)
        matched_rule_ids = filtered.pop("matched_rule_ids", [])

        return PolicyAuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            tenant_id=tenant_id,
            session_id=session_id,
            actor_id=actor_id,
            decision_id=decision_id,
            action=action,
            matched_rule_ids=matched_rule_ids,
            metadata=filtered,
        )

    def _emit(self, event: PolicyAuditEvent) -> None:
        """Flatten the event fields to top-level attributes and write to the audit logger."""
        log_fields: dict[str, Any] = {
            "timestamp": event.timestamp.isoformat(),
            "tenant_id": event.tenant_id,
        }
        if event.session_id is not None:
            log_fields["session_id"] = event.session_id
        if event.actor_id is not None:
            log_fields["actor_id"] = event.actor_id
        if event.decision_id is not None:
            log_fields["decision_id"] = event.decision_id
        if event.action is not None:
            log_fields["action"] = event.action.value if hasattr(event.action, "value") else str(event.action)  # noqa: E501
        if event.matched_rule_ids:
            log_fields["matched_rule_ids"] = event.matched_rule_ids

        # Merge metadata keys into top-level dictionary
        for k, v in event.metadata.items():
            log_fields[k] = v

        self._logger.info(event.event_type, **log_fields)

    async def publish_decision(self, ctx: ProcessingContext, decision: PolicyDecision) -> None:
        """Publish a policy decision event and record decision/denial metrics."""
        event = self._build_event(
            "policy_decision_recorded",
            tenant_id=ctx.tenant_id,
            session_id=ctx.request_id,
            decision_id=decision.enforcement or "unknown",
            action=decision.action,
            matched_rule_ids=decision.matched_rule_ids,
        )
        self._emit(event)

        # Increment metrics
        metrics = register_policy_metrics()
        action_str = decision.action.value if hasattr(decision.action, "value") else str(decision.action)  # noqa: E501
        metrics.record_decision(ctx.tenant_id, action_str)

        if decision.action == PolicyAction.BLOCK:
            reason_metric = decision.matched_rule_ids[0] if decision.matched_rule_ids else "blocked"
            metrics.record_denial(ctx.tenant_id, reason_metric)

    async def publish_rate_limit(self, tenant_id: str, limit_type: str, current: int, limit: int) -> None:  # noqa: E501
        """Publish a rate limit hit event and increment rate limit metrics."""
        event = self._build_event(
            "rate_limit_exceeded",
            tenant_id=tenant_id,
            limit_type=limit_type,
            current_value=current,
            limit=limit,
        )
        self._emit(event)

        metrics = register_policy_metrics()
        metrics.record_rate_limit(tenant_id, limit_type)

    async def publish_spend_limit(self, tenant_id: str, budget_type: str, current: Decimal, limit: Decimal, currency: str) -> None:  # noqa: E501
        """Publish a spend budget limit hit event and increment spend metrics."""
        event = self._build_event(
            "spend_limit_exceeded",
            tenant_id=tenant_id,
            budget_type=budget_type,
            current_spend=current,
            budget_limit=limit,
            currency=currency,
        )
        self._emit(event)

        metrics = register_policy_metrics()
        metrics.record_spend_limit(tenant_id, budget_type)

    async def publish_routing_violation(self, tenant_id: str, provider: str, region: str, allowed: list[str]) -> None:  # noqa: E501
        """Publish a residency routing violation event."""
        event = self._build_event(
            "routing_policy_violation",
            tenant_id=tenant_id,
            provider=provider,
            region=region,
            allowed_regions=allowed,
        )
        self._emit(event)

    async def publish_classification_block(self, tenant_id: str, classification: str, rule_id: str) -> None:  # noqa: E501
        """Publish a content classification block event."""
        event = self._build_event(
            "classification_block",
            tenant_id=tenant_id,
            classification_level=classification,
            matched_rule_id=rule_id,
        )
        self._emit(event)

    async def publish_budget_reset(self, tenant_id: str, budget_type: str) -> None:
        """Publish a spend budget reset boundary event."""
        event = self._build_event(
            "budget_reset",
            tenant_id=tenant_id,
            budget_type=budget_type,
            reset_at=datetime.now(UTC).isoformat(),
        )
        self._emit(event)
