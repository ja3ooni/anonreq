from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from anonreq.cache.manager import CacheManager
from anonreq.policy.models import PolicyAction, PolicyDecision, RateLimitConfig


class UsageLimiter:
    def __init__(self, cache_manager: CacheManager, config: RateLimitConfig) -> None:
        self._cache = cache_manager
        self._config = config

    def _rpm_key(self, tenant_id: str) -> str:
        window = int(time.time() / 60)
        return f"anonreq:ratelimit:{tenant_id}:rpm:{window}"

    def _tpm_key(self, tenant_id: str) -> str:
        window = int(time.time() / 60)
        return f"anonreq:ratelimit:{tenant_id}:tpm:{window}"

    def _concurrent_key(self, tenant_id: str) -> str:
        return f"anonreq:ratelimit:{tenant_id}:concurrent"

    async def check_rate_limit(self, tenant_id: str) -> PolicyDecision:
        try:
            now = datetime.now(timezone.utc)
            rpm_key = self._rpm_key(tenant_id)
            tpm_key = self._tpm_key(tenant_id)
            conc_key = self._concurrent_key(tenant_id)

            pipe = self._cache._redis.pipeline(transaction=True)
            pipe.incr(rpm_key)
            pipe.expire(rpm_key, 60)
            pipe.incr(tpm_key)
            pipe.expire(tpm_key, 60)
            pipe.get(conc_key)
            results = await pipe.execute()

            rpm_val = int(results[0])
            tpm_val = int(results[2])
            conc_val = int(results[4] or 0)

            reasons: list[str] = []
            if rpm_val > self._config.rpm:
                reasons.append(f"RPM limit exceeded: {rpm_val}/{self._config.rpm}")
            if tpm_val > self._config.tpm:
                reasons.append(f"TPM limit exceeded: {tpm_val}/{self._config.tpm}")
            if conc_val >= self._config.concurrent:
                reasons.append(f"Concurrent limit exceeded: {conc_val}/{self._config.concurrent}")

            if reasons:
                return PolicyDecision(
                    action=PolicyAction.BLOCK,
                    matched_rule_ids=["rate_limit"],
                    decision_ts=now,
                    reason="; ".join(reasons),
                )
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=["rate_limit"],
                decision_ts=now,
            )
        except Exception:
            return PolicyDecision(
                action=PolicyAction.BLOCK,
                matched_rule_ids=["rate_limit_error"],
                decision_ts=datetime.now(timezone.utc),
                reason="Rate limit check failed: cache unavailable",
                enforcement="503",
            )

    async def increment(self, tenant_id: str, tokens: int = 0) -> None:
        try:
            conc_key = self._concurrent_key(tenant_id)
            async with self._cache._redis.pipeline(transaction=True) as pipe:
                await pipe.incr(conc_key).execute()
        except Exception:
            pass

    async def decrement(self, tenant_id: str) -> None:
        try:
            conc_key = self._concurrent_key(tenant_id)
            async with self._cache._redis.pipeline(transaction=True) as pipe:
                await pipe.decr(conc_key).execute()
            val = await self._cache._redis.get(conc_key)
            if val is not None and int(val) < 0:
                await self._cache._redis.set(conc_key, 0)
        except Exception:
            pass

    async def get_current(self, tenant_id: str) -> dict[str, int]:
        """Return current counter values for the tenant without modifying them.

        Args:
            tenant_id: The tenant to query.

        Returns:
            Dict with rpm, tpm, and concurrent values.
        """
        try:
            rpm_key = self._rpm_key(tenant_id)
            tpm_key = self._tpm_key(tenant_id)
            conc_key = self._concurrent_key(tenant_id)

            pipe = self._cache._redis.pipeline(transaction=True)
            pipe.get(rpm_key)
            pipe.get(tpm_key)
            pipe.get(conc_key)
            results = await pipe.execute()

            return {
                "rpm": int(results[0] or 0),
                "tpm": int(results[1] or 0),
                "concurrent": int(results[2] or 0),
            }
        except Exception:
            return {"rpm": 0, "tpm": 0, "concurrent": 0}
