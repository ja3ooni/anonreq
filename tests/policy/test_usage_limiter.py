"""Tests for UsageLimiter."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from anonreq.cache.manager import CacheManager
from anonreq.policy.models import PolicyAction, RateLimitConfig
from anonreq.policy.usage_limiter import UsageLimiter


@pytest.fixture
def fake_cache():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mgr = CacheManager.__new__(CacheManager)
    mgr._redis = fake
    mgr._ttl = 300
    return mgr


@pytest.fixture
def limiter(fake_cache):
    config = RateLimitConfig(rpm=10, tpm=1000, concurrent=5)
    return UsageLimiter(fake_cache, config)


class TestUsageLimiterCheck:
    @pytest.mark.asyncio
    async def test_check_rate_limit_returns_allow_when_under_limits(self, limiter):
        decision = await limiter.check_rate_limit("tenant_under")
        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocks_when_rpm_exceeded(self, limiter):
        for _ in range(11):
            decision = await limiter.check_rate_limit("tenant_rpm_burst")
        assert decision.action == PolicyAction.BLOCK
        assert "RPM" in (decision.reason or "")

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocks_when_concurrent_exceeded(self, fake_cache, limiter):
        await fake_cache._redis.set("anonreq:ratelimit:tenant_conc:concurrent", 5)
        decision = await limiter.check_rate_limit("tenant_conc")
        assert decision.action == PolicyAction.BLOCK
        assert "concurrent" in (decision.reason or "").lower()

    @pytest.mark.asyncio
    async def test_check_rate_limit_returns_block_with_503_on_cache_error(self, fake_cache, limiter):  # noqa: E501
        from unittest.mock import patch

        with patch.object(fake_cache._redis, "pipeline", side_effect=Exception("Connection refused")):  # noqa: E501
            decision = await limiter.check_rate_limit("tenant_error")
        assert decision.action == PolicyAction.BLOCK
        assert decision.enforcement == "503"

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocks_when_tpm_exceeded(self, limiter):
        import time
        window = int(time.time() / 60)
        tpm_key = f"anonreq:ratelimit:tenant_tpm:tpm:{window}"
        await limiter._cache._redis.set(tpm_key, 1000)
        await limiter._cache._redis.expire(tpm_key, 60)
        decision = await limiter.check_rate_limit("tenant_tpm")
        assert decision.action == PolicyAction.BLOCK
        assert "TPM" in (decision.reason or "")


class TestUsageLimiterIncrement:
    @pytest.mark.asyncio
    async def test_increment_increases_counters(self, fake_cache, limiter):
        await limiter.increment("tenant_incr", tokens=5)
        conc = await fake_cache._redis.get("anonreq:ratelimit:tenant_incr:concurrent")
        assert conc == "1"

    @pytest.mark.asyncio
    async def test_increment_multiple_times(self, fake_cache, limiter):
        await limiter.increment("tenant_multi")
        await limiter.increment("tenant_multi")
        await limiter.increment("tenant_multi")
        conc = await fake_cache._redis.get("anonreq:ratelimit:tenant_multi:concurrent")
        assert conc == "3"


class TestUsageLimiterDecrement:
    @pytest.mark.asyncio
    async def test_decrement_releases_concurrent_slot(self, fake_cache, limiter):
        await fake_cache._redis.set("anonreq:ratelimit:tenant_dec:concurrent", 3)
        await limiter.decrement("tenant_dec")
        conc = await fake_cache._redis.get("anonreq:ratelimit:tenant_dec:concurrent")
        assert conc == "2"

    @pytest.mark.asyncio
    async def test_decrement_floor_is_zero(self, fake_cache, limiter):
        await limiter.decrement("tenant_floor")
        conc = await fake_cache._redis.get("anonreq:ratelimit:tenant_floor:concurrent")
        assert conc is None or conc == "0"

    @pytest.mark.asyncio
    async def test_increment_decrement_balance(self, fake_cache, limiter):
        await limiter.increment("tenant_bal")
        await limiter.increment("tenant_bal")
        await limiter.decrement("tenant_bal")
        conc = await fake_cache._redis.get("anonreq:ratelimit:tenant_bal:concurrent")
        assert conc == "1"


class TestUsageLimiterFailClosed:
    @pytest.mark.asyncio
    async def test_increment_fail_closed_on_cache_error(self, fake_cache, limiter):
        from unittest.mock import patch

        with patch.object(fake_cache._redis, "pipeline", side_effect=Exception("Connection refused")):  # noqa: E501
            await limiter.increment("tenant_fail")

    @pytest.mark.asyncio
    async def test_decrement_fail_safe_recovery(self, fake_cache, limiter):
        from unittest.mock import patch

        with patch.object(fake_cache._redis, "pipeline", side_effect=Exception("Connection refused")):  # noqa: E501
            await limiter.decrement("tenant_fail_safe")
