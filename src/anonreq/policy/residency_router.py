from __future__ import annotations

from datetime import datetime, timezone

from anonreq.policy.models import PolicyAction, PolicyDecision, ResidencyRule


class ResidencyRouter:
    def __init__(self, rules: dict[str, ResidencyRule]) -> None:
        self._rules = rules

    async def resolve_region(
        self,
        tenant_id: str,
        provider_region: str,
        provider_name: str,
    ) -> PolicyDecision:
        now = datetime.now(timezone.utc)
        rule = self._rules.get(tenant_id)
        if rule is None:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=[],
                decision_ts=now,
                reason="No residency rules for tenant",
            )

        if provider_region in rule.allowed_regions:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=["residency_match"],
                decision_ts=now,
                reason=f"Region {provider_region} is allowed",
            )

        if provider_region in rule.blocked_regions:
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["residency_block"],
                decision_ts=now,
                reason=f"Region {provider_region} is blocked",
            )

        return PolicyDecision(
            action=rule.fallback_action,
            matched_rule_ids=["residency_fallback"],
            decision_ts=now,
            reason=f"Region {provider_region} not in allowed or blocked lists, using fallback",
        )
