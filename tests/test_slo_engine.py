"""Unit tests for SLOEngine."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
import pytest

from anonreq.services.slo_engine import SLOEngine


@pytest.mark.asyncio
async def test_slo_increment_success_failure(cache_manager):
    # Initialize engine with default config fallback
    engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")

    # Record 4 successes and 1 failure for success_rate
    await engine.record_success("tenant_test", "success_rate")
    await engine.record_success("tenant_test", "success_rate")
    await engine.record_success("tenant_test", "success_rate")
    await engine.record_success("tenant_test", "success_rate")
    await engine.record_failure("tenant_test", "success_rate")

    # Compute compliance
    compliance = await engine.compute_compliance("tenant_test", "success_rate")
    
    # We should have daily, monthly, 24h, 30d windows
    assert len(compliance) == 4
    for c in compliance:
        assert c.slo_name == "success_rate"
        assert c.target == 99.9
        # 4 successes out of 5 total = 80.0%
        assert c.current == 80.0
        assert c.compliant is False


@pytest.mark.asyncio
async def test_slo_p95_latency_computation(cache_manager):
    engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")

    # Record 100 latency observations from 1ms to 100ms
    for i in range(1, 101):
        await engine.record_latency("tenant_test", i)

    compliance = await engine.compute_compliance("tenant_test", "p95_latency_ms")
    
    assert len(compliance) == 4
    for c in compliance:
        assert c.slo_name == "p95_latency_ms"
        assert c.target == 100.0
        # P95 of [1..100] is 96.0 (at index 95)
        assert c.current == 96.0
        assert c.compliant is True


@pytest.mark.asyncio
async def test_slo_empty_counters_return_100_percent(cache_manager):
    engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")

    compliance = await engine.compute_compliance("tenant_test", "success_rate")
    for c in compliance:
        assert c.current == 100.0
        assert c.compliant is True


@pytest.mark.asyncio
async def test_slo_config_target_override(cache_manager):
    # Test with real slo.yaml config
    engine = SLOEngine(cache_manager, config_path="config/slo.yaml")
    compliance = await engine.compute_compliance("tenant_test", "success_rate")
    assert len(compliance) > 0
    assert compliance[0].target == 99.9


@pytest.mark.asyncio
async def test_slo_rolling_window_expiry(cache_manager):
    engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")

    # We mock rolling key directly to test time-based eviction
    tenant_id = "tenant_test"
    slo_name = "success_rate"
    
    # We will record success events directly with past timestamps
    now = time.time()
    past_25h = now - 90000
    
    den_key = f"slo:{tenant_id}:{slo_name}:rolling:24h:den"
    num_key = f"slo:{tenant_id}:{slo_name}:rolling:24h:num"

    # Store 1 old event (25h ago) and 1 new event (now)
    await cache_manager._redis.zadd(den_key, {"old_evt": past_25h, "new_evt": now})
    await cache_manager._redis.zadd(num_key, {"new_evt": now})

    # Compute compliance (should trigger zremrangebyscore)
    compliance = await engine.compute_compliance(tenant_id, slo_name)
    
    c_24h = next(c for c in compliance if c.window_type == "24h")
    # Old event is evicted, so denominator = 1, numerator = 1 -> 100% compliance!
    assert c_24h.current == 100.0
    assert c_24h.compliant is True
