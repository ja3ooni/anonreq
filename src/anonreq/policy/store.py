from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from anonreq.cache.manager import CacheManager
from anonreq.policy.config import PolicyConfig
from anonreq.policy.models import PolicyAction, PolicyRule


def _rule_to_dict(rule: PolicyRule) -> dict:
    d = rule.model_dump()
    if d.get("conditions") is None:
        d["conditions"] = {}
    if d.get("description") is None:
        d["description"] = ""
    if d.get("tenant_id") is None:
        d["tenant_id"] = ""
    return d


def _dict_to_rule(d: dict) -> PolicyRule:
    if d.get("description") == "":
        d["description"] = None
    if d.get("tenant_id") == "":
        d["tenant_id"] = None
    if d.get("conditions") == {}:
        d["conditions"] = None
    return PolicyRule.model_validate(d)


class PolicyStore:
    def __init__(self, cache_manager: CacheManager, policy_config: PolicyConfig) -> None:
        self._cache = cache_manager
        self._config = policy_config
        self._global_rules = [r for r in policy_config.rules if r.tenant_id is None]
        self._tenant_rules: dict[str, list[PolicyRule]] = {}
        for r in policy_config.rules:
            if r.tenant_id is not None:
                self._tenant_rules.setdefault(r.tenant_id, []).append(r)

    def _policy_key(self, tenant_id: str, suffix: str = "rules") -> str:
        return f"anonreq:policy:{tenant_id}:{suffix}"

    def _version_hash(self) -> str:
        raw = json.dumps(
            [r.model_dump() for r in self._config.rules],
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def load_policies(self, tenant_id: str) -> list[PolicyRule]:
        cache_key = self._policy_key(tenant_id)
        cached = await self._cache._redis.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            return [_dict_to_rule(d) for d in data]

        rules = list(self._global_rules)
        if tenant_id in self._tenant_rules:
            rules.extend(self._tenant_rules[tenant_id])

        serialized = json.dumps([_rule_to_dict(r) for r in rules], default=str)
        async with self._cache._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.set(cache_key, serialized)
                .expire(cache_key, 300)
                .set(self._policy_key(tenant_id, "version"), self._version_hash())
                .execute()
            )
        return rules

    async def get_policy(self, rule_id: str, tenant_id: str | None = None) -> PolicyRule | None:
        if tenant_id:
            rules = await self.load_policies(tenant_id)
            for r in rules:
                if r.rule_id == rule_id:
                    return r
        for r in self._global_rules:
            if r.rule_id == rule_id:
                return r
        return None

    async def enabled_rules(self, tenant_id: str) -> list[PolicyRule]:
        all_rules = await self.load_policies(tenant_id)
        return sorted(
            [r for r in all_rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )

    async def set_tenant_policy(self, tenant_id: str, rules: list[PolicyRule]) -> None:
        serialized = json.dumps([_rule_to_dict(r) for r in rules], default=str)
        async with self._cache._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.set(self._policy_key(tenant_id), serialized)
                .expire(self._policy_key(tenant_id), 300)
                .set(self._policy_key(tenant_id, "version"), self._version_hash())
                .execute()
            )
        self._tenant_rules[tenant_id] = rules

    async def invalidate_cache(self, tenant_id: str | None = None) -> None:
        if tenant_id is not None:
            await self._cache._redis.delete(
                self._policy_key(tenant_id),
                self._policy_key(tenant_id, "version"),
            )
        else:
            cursor = 0
            pattern = "anonreq:policy:*"
            while True:
                cursor, keys = await self._cache._redis.scan(cursor=cursor, match=pattern)
                if keys:
                    await self._cache._redis.delete(*keys)
                if cursor == 0:
                    break
