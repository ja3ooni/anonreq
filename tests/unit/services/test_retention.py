"""Unit tests for RetentionService."""

from __future__ import annotations

import pytest

from anonreq.services.retention import RetentionService


@pytest.fixture
def fake_redis():
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    return fakeredis.FakeRedis()


@pytest.fixture
def retention_service(fake_redis) -> RetentionService:
    from anonreq.cache.manager import CacheManager

    cache = CacheManager._from_client(fake_redis, ttl=300)
    return RetentionService(cache_manager=cache)


@pytest.mark.unit
class TestRetentionService:
    @pytest.mark.anyio
    async def test_set_and_get_policy(self, retention_service: RetentionService) -> None:
        policy = await retention_service.set_policy("audit_event", 2557, "delete")
        assert policy.record_type == "audit_event"
        assert policy.retention_days == 2557

        fetched = await retention_service.get_policy("audit_event")
        assert fetched is not None
        assert fetched.retention_days == 2557

    @pytest.mark.anyio
    async def test_get_missing_policy_returns_none(
        self, retention_service: RetentionService
    ) -> None:
        result = await retention_service.get_policy("nonexistent")
        assert result is None

    @pytest.mark.anyio
    async def test_list_policies(self, retention_service: RetentionService) -> None:
        await retention_service.set_policy("audit_event", 365, "delete")
        await retention_service.set_policy("user_data", 90, "anonymize")
        policies = await retention_service.list_policies()
        assert len(policies) >= 2

    @pytest.mark.anyio
    async def test_impose_and_release_hold(self, retention_service: RetentionService) -> None:
        hold = await retention_service.impose_hold(
            record_types=["audit_event"],
            tenant_id="tenant-1",
            hold_ref="LIT-2024-001",
            imposed_by="legal@corp.com",
        )
        assert hold.hold_id is not None
        assert hold.tenant_id == "tenant-1"

        released = await retention_service.release_hold(hold.hold_id, "legal@corp.com")
        assert released.released_at is not None

    @pytest.mark.anyio
    async def test_release_nonexistent_hold_raises(
        self, retention_service: RetentionService
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            await retention_service.release_hold("fake-hold-id", "user")

    @pytest.mark.anyio
    async def test_is_hold_active(self, retention_service: RetentionService) -> None:
        await retention_service.impose_hold(
            record_types=["audit_event"],
            tenant_id="tenant-1",
            hold_ref="LIT-2024-002",
            imposed_by="legal@corp.com",
        )
        assert await retention_service.is_hold_active("audit_event", "tenant-1") is True
        assert await retention_service.is_hold_active("user_data", "tenant-1") is False
        assert await retention_service.is_hold_active("audit_event", "tenant-2") is False

    @pytest.mark.anyio
    async def test_released_hold_not_active(self, retention_service: RetentionService) -> None:
        hold = await retention_service.impose_hold(
            record_types=["audit_event"],
            tenant_id="tenant-1",
            hold_ref="LIT-2024-003",
            imposed_by="legal@corp.com",
        )
        await retention_service.release_hold(hold.hold_id, "legal@corp.com")
        assert await retention_service.is_hold_active("audit_event", "tenant-1") is False
