from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import structlog
from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision
from anonreq.policy.residency_router import ResidencyRouter
from anonreq.policy.spend_controller import SpendController
from anonreq.policy.store import PolicyStore
from anonreq.policy.usage_limiter import UsageLimiter

logger = get_logger("anonreq.policy.pdp")


class PolicyDecisionPoint:
    def __init__(
        self,
        policy_store: PolicyStore,
        usage_limiter: UsageLimiter,
        spend_controller: SpendController,
        residency_router: ResidencyRouter,
        cache_ttl: int = 5,
    ) -> None:
        self._policy_store = policy_store
        self._usage_limiter = usage_limiter
        self._spend_controller = spend_controller
        self._residency_router = residency_router
        self._cache_ttl = cache_ttl
        self._decision_cache: dict[str, tuple[float, PolicyDecision]] = {}

    def _compute_request_hash(self, ctx: ProcessingContext) -> str:
        raw = json.dumps({
            "tenant_id": ctx.tenant_id,
            "model": ctx.model or "",
            "classification": (
                ctx.classification_result or {}
            ).get("classification_level", ""),
            "provider": ctx.provider or "",
        }, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cache_key(self, tenant_id: str, request_hash: str) -> str:
        return f"{tenant_id}:{request_hash}"

    def _get_cached(self, tenant_id: str, request_hash: str) -> PolicyDecision | None:
        key = self._cache_key(tenant_id, request_hash)
        entry = self._decision_cache.get(key)
        if entry is not None:
            ts, decision = entry
            if time.monotonic() - ts < self._cache_ttl:
                return decision
            del self._decision_cache[key]
        return None

    def _set_cache(self, tenant_id: str, request_hash: str, decision: PolicyDecision) -> None:
        key = self._cache_key(tenant_id, request_hash)
        self._decision_cache[key] = (time.monotonic(), decision)

    async def evaluate_classification(
        self, tenant_id: str, classification_result: dict | None,
    ) -> PolicyDecision:
        try:
            rules = await self._policy_store.enabled_rules(tenant_id)
            classification_level = (
                (classification_result or {}).get("classification_level", "")
            )
            for rule in rules:
                if not rule.conditions:
                    continue
                rule_level = rule.conditions.get("classification_level", "")
                if rule_level and rule_level == classification_level:
                    return PolicyDecision(
                        action=rule.action,
                        matched_rule_ids=[rule.rule_id],
                        decision_ts=datetime.now(timezone.utc),
                        ttl_seconds=self._cache_ttl,
                        reason=f"Classification rule '{rule.rule_id}' matched level '{classification_level}'",
                    )
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=[],
                decision_ts=datetime.now(timezone.utc),
                ttl_seconds=self._cache_ttl,
            )
        except Exception as exc:
            logger.error("pdp.classification_error", error=str(exc), tenant_id=tenant_id)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["classification_error"],
                decision_ts=datetime.now(timezone.utc),
                reason="Classification evaluation failed",
                enforcement="503",
            )

    async def evaluate_rate_limit(self, tenant_id: str) -> PolicyDecision:
        try:
            return await self._usage_limiter.check_rate_limit(tenant_id)
        except Exception as exc:
            logger.error("pdp.rate_limit_error", error=str(exc), tenant_id=tenant_id)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["rate_limit_error"],
                decision_ts=datetime.now(timezone.utc),
                reason="Rate limit evaluation failed",
                enforcement="503",
            )

    async def evaluate_spend(self, tenant_id: str) -> PolicyDecision:
        try:
            return await self._spend_controller.check_spend(tenant_id)
        except Exception as exc:
            logger.error("pdp.spend_error", error=str(exc), tenant_id=tenant_id)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["spend_error"],
                decision_ts=datetime.now(timezone.utc),
                reason="Spend evaluation failed",
                enforcement="503",
            )

    async def evaluate_residency(
        self, tenant_id: str, provider: str | None, region: str | None,
    ) -> PolicyDecision:
        try:
            provider_name = provider or "unknown"
            provider_region = region or "unknown"
            return await self._residency_router.resolve_region(
                tenant_id, provider_region, provider_name,
            )
        except Exception as exc:
            logger.error("pdp.residency_error", error=str(exc), tenant_id=tenant_id)
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["residency_error"],
                decision_ts=datetime.now(timezone.utc),
                reason="Residency evaluation failed",
                enforcement="503",
            )

    async def evaluate_all(self, ctx: ProcessingContext) -> PolicyDecision:
        request_hash = self._compute_request_hash(ctx)

        cached = self._get_cached(ctx.tenant_id, request_hash)
        if cached is not None:
            return cached

        class_result = await self.evaluate_classification(
            ctx.tenant_id, ctx.classification_result,
        )
        if class_result.action == PolicyAction.BLOCK:
            self._set_cache(ctx.tenant_id, request_hash, class_result)
            return class_result

        rate_result = await self.evaluate_rate_limit(ctx.tenant_id)
        if rate_result.action == PolicyAction.BLOCK:
            self._set_cache(ctx.tenant_id, request_hash, rate_result)
            return rate_result

        spend_result = await self.evaluate_spend(ctx.tenant_id)
        if spend_result.action == PolicyAction.BLOCK:
            self._set_cache(ctx.tenant_id, request_hash, spend_result)
            return spend_result

        residency_result = await self.evaluate_residency(
            ctx.tenant_id, ctx.provider, None,
        )
        if residency_result.action == PolicyAction.BLOCK:
            self._set_cache(ctx.tenant_id, request_hash, residency_result)
            return residency_result

        allow = PolicyDecision(
            action=PolicyAction.ALLOW,
            matched_rule_ids=["all_checks_passed"],
            decision_ts=datetime.now(timezone.utc),
            ttl_seconds=self._cache_ttl,
        )
        self._set_cache(ctx.tenant_id, request_hash, allow)
        return allow
