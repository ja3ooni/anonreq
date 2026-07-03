"""Tests for SpendController."""

from __future__ import annotations

from decimal import Decimal

import fakeredis.aioredis
import pytest

from anonreq.cache.manager import CacheManager
from anonreq.policy.models import PolicyAction, SpendBudget
from anonreq.policy.spend_controller import SpendController


@pytest.fixture
def fake_cache():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mgr = CacheManager.__new__(CacheManager)
    mgr._redis = fake
    mgr._ttl = 300
    yield mgr


@pytest.fixture
def controller(fake_cache):
    budgets = {
        "tenant_acme": SpendBudget(daily_usd=Decimal("100"), monthly_usd=Decimal("3000")),
    }
    return SpendController(fake_cache, budgets)


class TestSpendControllerCheck:
    @pytest.mark.asyncio
    async def test_check_spend_returns_allow_when_under_budget(self, controller):
        decision = await controller.check_spend("tenant_acme")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_check_spend_blocks_when_daily_exceeded(self, fake_cache, controller):
        await fake_cache._redis.set("anonreq:spend:tenant_acme:daily", "150.00")
        decision = await controller.check_spend("tenant_acme")
        assert decision.action == PolicyAction.BLOCK
        assert "daily" in (decision.reason or "").lower()

    @pytest.mark.asyncio
    async def test_check_spend_blocks_when_monthly_exceeded(self, fake_cache, controller):
        await fake_cache._redis.set("anonreq:spend:tenant_acme:monthly", "3500.00")
        decision = await controller.check_spend("tenant_acme")
        assert decision.action == PolicyAction.BLOCK
        assert "monthly" in (decision.reason or "").lower()

    @pytest.mark.asyncio
    async def test_check_spend_returns_allow_for_unknown_tenant(self, controller):
        decision = await controller.check_spend("unknown_tenant")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_check_spend_fail_closed_on_cache_error(self, fake_cache, controller):
        from unittest.mock import patch

        with patch.object(fake_cache._redis, "pipeline", side_effect=Exception("Connection refused")):
            decision = await controller.check_spend("tenant_acme")
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"


class TestSpendControllerRecord:
    @pytest.mark.asyncio
    async def test_record_spend_adds_to_daily(self, fake_cache, controller):
        await controller.record_spend("tenant_acme", Decimal("25.50"))
        daily = await fake_cache._redis.get("anonreq:spend:tenant_acme:daily")
        assert daily is not None
        assert float(daily) >= 25.0

    @pytest.mark.asyncio
    async def test_record_spend_adds_to_monthly(self, fake_cache, controller):
        await controller.record_spend("tenant_acme", Decimal("50.00"))
        monthly = await fake_cache._redis.get("anonreq:spend:tenant_acme:monthly")
        assert monthly is not None
        assert float(monthly) >= 50.0

    @pytest.mark.asyncio
    async def test_record_spend_accumulates(self, fake_cache, controller):
        await controller.record_spend("tenant_acme", Decimal("10"))
        await controller.record_spend("tenant_acme", Decimal("20"))
        await controller.record_spend("tenant_acme", Decimal("30"))
        daily = await fake_cache._redis.get("anonreq:spend:tenant_acme:daily")
        assert daily is not None
        assert float(daily) >= 59.0

    @pytest.mark.asyncio
    async def test_record_spend_handles_cache_error(self, fake_cache, controller):
        from unittest.mock import patch

        with patch.object(fake_cache._redis, "pipeline", side_effect=Exception("Connection refused")):
            await controller.record_spend("tenant_acme", Decimal("10"))


class TestSpendControllerGetUsage:
    @pytest.mark.asyncio
    async def test_get_usage_returns_record(self, fake_cache, controller):
        await controller.record_spend("tenant_acme", Decimal("15.00"))
        record = await controller.get_usage("tenant_acme")
        assert record.tenant_id == "tenant_acme"
        assert record.daily_spend >= Decimal("15.00")
