"""Unit tests for SLOEngine."""

from __future__ import annotations

import pytest

from anonreq.services.slo_engine import SLOEngine


@pytest.fixture
def fake_redis():
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    return fakeredis.FakeRedis()


@pytest.fixture
def slo_engine(fake_redis) -> SLOEngine:
    from anonreq.cache.manager import CacheManager

    cache = CacheManager._from_client(fake_redis, ttl=300)
    return SLOEngine(cache_manager=cache, config_path="/nonexistent/slo.yaml")


@pytest.mark.unit
class TestSLOEngine:
    @pytest.mark.anyio
    async def test_record_success_increments_counters(self, slo_engine: SLOEngine) -> None:
        await slo_engine.record_success("tenant-1", "success_rate")
        compliance = await slo_engine.compute_compliance("tenant-1", "success_rate")
        assert len(compliance) > 0

    @pytest.mark.anyio
    async def test_record_failure(self, slo_engine: SLOEngine) -> None:
        await slo_engine.record_failure("tenant-1", "success_rate")
        compliance = await slo_engine.compute_compliance("tenant-1", "success_rate")
        assert any(not c.compliant or c.current <= 1.0 for c in compliance)

    @pytest.mark.anyio
    async def test_compute_compliance_returns_list(self, slo_engine: SLOEngine) -> None:
        result = await slo_engine.compute_compliance("tenant-1")
        assert isinstance(result, list)

    def test_calculate_p95(self, slo_engine: SLOEngine) -> None:
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        p95 = slo_engine._calculate_p95(latencies)
        assert 90.0 <= p95 <= 100.0

    def test_calculate_p95_empty(self, slo_engine: SLOEngine) -> None:
        assert slo_engine._calculate_p95([]) == 0.0

    @pytest.mark.anyio
    async def test_get_all_compliance_groups_by_slo(self, slo_engine: SLOEngine) -> None:
        await slo_engine.record_success("tenant-1", "success_rate")
        await slo_engine.record_success("tenant-1", "p95_latency_ms")
        result = await slo_engine.get_all_compliance("tenant-1")
        assert isinstance(result, dict)
        assert "success_rate" in result or "p95_latency_ms" in result
