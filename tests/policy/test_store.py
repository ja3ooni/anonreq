"""Tests for PolicyStore with Valkey-backed versioned cache."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from anonreq.cache.manager import CacheManager
from anonreq.policy.config import PolicyConfig
from anonreq.policy.models import PolicyAction, PolicyRule
from anonreq.policy.store import PolicyStore


@pytest.fixture
def fake_cache_manager():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mgr = CacheManager.__new__(CacheManager)
    mgr._redis = fake
    mgr._ttl = 300
    return mgr


@pytest.fixture
def policy_config():
    return PolicyConfig(
        version="1.0",
        rules=[
            PolicyRule(
                rule_id="block_hr",
                name="Block HR",
                action=PolicyAction.BLOCK,
                priority=100,
                enabled=True,
                conditions={"classification_level": "Highly Restricted"},
            ),
            PolicyRule(
                rule_id="flag_conf",
                name="Flag Conf",
                action=PolicyAction.FLAG_AND_FORWARD,
                priority=50,
                enabled=True,
                conditions={"classification_level": "Confidential"},
            ),
            PolicyRule(
                rule_id="allow_default",
                name="Allow Default",
                action=PolicyAction.ALLOW,
                priority=0,
                enabled=True,
            ),
            PolicyRule(
                rule_id="disabled_rule",
                name="Disabled",
                action=PolicyAction.MONITOR,
                priority=10,
                enabled=False,
            ),
        ],
        spend_budgets={},
        residency_rules={},
    )


@pytest.fixture
async def policy_store(fake_cache_manager, policy_config):
    store = PolicyStore(fake_cache_manager, policy_config)
    yield store
    await fake_cache_manager.close()


class TestPolicyStoreLoad:
    @pytest.mark.asyncio
    async def test_load_policies_returns_tenant_rules(self, policy_store):
        rules = await policy_store.load_policies("tenant_test")
        assert len(rules) == 4
        rule_ids = [r.rule_id for r in rules]
        assert "block_hr" in rule_ids
        assert "allow_default" in rule_ids

    @pytest.mark.asyncio
    async def test_load_policies_caches_result(self, policy_store):
        rules1 = await policy_store.load_policies("tenant_cache_test")
        rules2 = await policy_store.load_policies("tenant_cache_test")
        assert rules1 == rules2


class TestPolicyStoreGet:
    @pytest.mark.asyncio
    async def test_get_policy_returns_rule_by_id(self, policy_store):
        rule = await policy_store.get_policy("block_hr")
        assert rule is not None
        assert rule.rule_id == "block_hr"
        assert rule.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_get_policy_returns_none_for_unknown(self, policy_store):
        rule = await policy_store.get_policy("nonexistent_rule")
        assert rule is None

    @pytest.mark.asyncio
    async def test_get_policy_with_tenant_scope(self, policy_store):
        await policy_store.set_tenant_policy("tenant_a", [
            PolicyRule(rule_id="tenant_only", name="Tenant Rule", action=PolicyAction.BLOCK),
        ])
        rule = await policy_store.get_policy("tenant_only", tenant_id="tenant_a")
        assert rule is not None
        assert rule.rule_id == "tenant_only"


class TestPolicyStoreEnabledRules:
    @pytest.mark.asyncio
    async def test_enabled_rules_excludes_disabled(self, policy_store):
        rules = await policy_store.enabled_rules("tenant_test")
        rule_ids = [r.rule_id for r in rules]
        assert "disabled_rule" not in rule_ids

    @pytest.mark.asyncio
    async def test_enabled_rules_sorted_by_priority_desc(self, policy_store):
        rules = await policy_store.enabled_rules("tenant_test")
        assert len(rules) >= 3
        assert rules[0].rule_id == "block_hr"
        assert rules[1].rule_id == "flag_conf"
        assert rules[2].rule_id == "allow_default"


class TestPolicyStoreTenantPolicy:
    @pytest.mark.asyncio
    async def test_set_tenant_policy_persists(self, policy_store):
        tenant_rules = [
            PolicyRule(rule_id="tenant_specific", name="Tenant Specific", action=PolicyAction.ROUTE_LOCAL),  # noqa: E501
        ]
        await policy_store.set_tenant_policy("tenant_b", tenant_rules)
        rules = await policy_store.load_policies("tenant_b")
        rule_ids = [r.rule_id for r in rules]
        assert "tenant_specific" in rule_ids

    @pytest.mark.asyncio
    async def test_tenant_with_no_config_gets_global_defaults(self, policy_store):
        rules = await policy_store.load_policies("new_tenant")
        rule_ids = [r.rule_id for r in rules]
        assert "block_hr" in rule_ids
        assert "allow_default" in rule_ids


class TestPolicyStoreInvalidate:
    @pytest.mark.asyncio
    async def test_invalidate_cache_clears_tenant(self, policy_store, fake_cache_manager):
        await policy_store.load_policies("tenant_inval")
        cache_key = "anonreq:policy:tenant_inval:rules"
        cached = await fake_cache_manager._redis.get(cache_key)
        assert cached is not None

        await policy_store.invalidate_cache("tenant_inval")
        cached_after = await fake_cache_manager._redis.get(cache_key)
        assert cached_after is None

    @pytest.mark.asyncio
    async def test_invalidate_all_clears_all_tenants(self, policy_store, fake_cache_manager):
        await policy_store.load_policies("tenant_x")
        await policy_store.load_policies("tenant_y")
        await policy_store.invalidate_cache()
        assert await fake_cache_manager._redis.get("anonreq:policy:tenant_x:rules") is None
        assert await fake_cache_manager._redis.get("anonreq:policy:tenant_y:rules") is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_tenant_does_not_raise(self, policy_store):
        await policy_store.invalidate_cache("nonexistent_tenant")


class TestPolicyStoreVersioning:
    @pytest.mark.asyncio
    async def test_version_pinned_cache_detects_stale(self, policy_store, fake_cache_manager):
        await policy_store.load_policies("tenant_ver")
        version_key = "anonreq:policy:tenant_ver:version"
        version = await fake_cache_manager._redis.get(version_key)
        assert version is not None

        await fake_cache_manager._redis.set(version_key + ":stale", "1")
        await policy_store.invalidate_cache("tenant_ver")
        cached = await fake_cache_manager._redis.get("anonreq:policy:tenant_ver:rules")
        assert cached is None
