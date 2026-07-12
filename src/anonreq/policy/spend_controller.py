from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from anonreq.cache.manager import CacheManager
from anonreq.policy.models import PolicyAction, PolicyDecision, SpendBudget, UsageRecord


class SpendController:
    def __init__(self, cache_manager: CacheManager, budgets: dict[str, SpendBudget]) -> None:
        self._cache = cache_manager
        self._budgets = budgets

    def _daily_key(self, tenant_id: str) -> str:
        return f"anonreq:spend:{tenant_id}:daily"

    def _monthly_key(self, tenant_id: str) -> str:
        return f"anonreq:spend:{tenant_id}:monthly"

    def _daily_ttl(self) -> int:
        now = datetime.now(UTC)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = tomorrow.replace(day=tomorrow.day + 1)
        return int((tomorrow - now).total_seconds())

    def _monthly_ttl(self) -> int:
        now = datetime.now(UTC)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        next_month = next_month.replace(hour=0, minute=0, second=0, microsecond=0)
        return int((next_month - now).total_seconds())

    async def check_spend(self, tenant_id: str) -> PolicyDecision:
        try:
            now = datetime.now(UTC)
            budget = self._budgets.get(tenant_id)
            if budget is None or not budget.enabled:
                return PolicyDecision(
                    action=PolicyAction.ALLOW,
                    matched_rule_ids=[],
                    decision_ts=now,
                )

            daily_key = self._daily_key(tenant_id)
            monthly_key = self._monthly_key(tenant_id)

            pipe = self._cache._redis.pipeline(transaction=True)
            pipe.get(daily_key)
            pipe.get(monthly_key)
            results = await pipe.execute()

            daily_raw = results[0]
            monthly_raw = results[1]

            reasons: list[str] = []
            if daily_raw is not None and budget.daily_usd is not None:
                daily_spend = Decimal(str(daily_raw))
                if daily_spend >= budget.daily_usd:
                    reasons.append(
                        f"Daily spend limit exceeded: ${daily_spend:.2f}/${budget.daily_usd:.2f}"
                    )
            if monthly_raw is not None and budget.monthly_usd is not None:
                monthly_spend = Decimal(str(monthly_raw))
                if monthly_spend >= budget.monthly_usd:
                    reasons.append(
                        f"Monthly spend limit exceeded: ${monthly_spend:.2f}/${budget.monthly_usd:.2f}"  # noqa: E501
                    )

            if reasons:
                return PolicyDecision(
                    action=PolicyAction.BLOCK,
                    matched_rule_ids=["spend_limit"],
                    decision_ts=now,
                    reason="; ".join(reasons),
                )
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=["spend_limit"],
                decision_ts=now,
            )
        except Exception:
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["spend_limit_error"],
                decision_ts=datetime.now(UTC),
                reason="Spend check failed: cache unavailable",
                enforcement="503",
            )

    async def record_spend(self, tenant_id: str, cost: Decimal) -> None:
        try:
            daily_key = self._daily_key(tenant_id)
            monthly_key = self._monthly_key(tenant_id)
            daily_ttl = self._daily_ttl()
            monthly_ttl = self._monthly_ttl()

            async with self._cache._redis.pipeline(transaction=True) as pipe:
                await (
                    pipe.incrbyfloat(daily_key, float(cost))
                    .expire(daily_key, daily_ttl)
                    .incrbyfloat(monthly_key, float(cost))
                    .expire(monthly_key, monthly_ttl)
                    .execute()
                )
        except Exception:
            pass

    async def get_usage(self, tenant_id: str) -> UsageRecord:
        now = datetime.now(UTC)
        try:
            daily_key = self._daily_key(tenant_id)
            monthly_key = self._monthly_key(tenant_id)
            pipe = self._cache._redis.pipeline(transaction=True)
            pipe.get(daily_key)
            pipe.get(monthly_key)
            results = await pipe.execute()
            daily = Decimal(str(results[0])) if results[0] else Decimal("0")
            monthly = Decimal(str(results[1])) if results[1] else Decimal("0")
        except Exception:
            daily = Decimal("0")
            monthly = Decimal("0")
        return UsageRecord(
            tenant_id=tenant_id,
            rpm_current=0,
            tpm_current=0,
            concurrent_current=0,
            daily_spend=daily,
            monthly_spend=monthly,
            reset_at=now,
        )
