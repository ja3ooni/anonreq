"""Tests for retention management with Legal Hold support.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import pytest

from anonreq.services.retention import (
    RetentionService,
)


@pytest.fixture
async def retention_service(cache_manager):
    svc = RetentionService(cache_manager)
    keys = await svc._redis.keys("anonreq:retention:*")
    for k in keys:
        await svc._redis.delete(k)
    keys = await svc._redis.keys("anonreq:legalhold:*")
    for k in keys:
        await svc._redis.delete(k)
    return svc


class TestRetentionPolicy:
    async def test_set_policy_returns_policy(self, retention_service):
        policy = await retention_service.set_policy(
            record_type="audit_logs",
            retention_days=2557,
            disposition_action="archive",
        )
        assert policy.record_type == "audit_logs"
        assert policy.retention_days == 2557
        assert policy.disposition_action == "archive"

    async def test_get_policy_returns_none_for_unset(self, retention_service):
        policy = await retention_service.get_policy("no-such")
        assert policy is None

    async def test_get_policy_after_set(self, retention_service):
        await retention_service.set_policy("audit_logs", 2557, "delete")
        policy = await retention_service.get_policy("audit_logs")
        assert policy is not None
        assert policy.retention_days == 2557

    async def test_set_policy_updates_existing(self, retention_service):
        await retention_service.set_policy("audit_logs", 90, "delete")
        await retention_service.set_policy("audit_logs", 365, "archive")
        policy = await retention_service.get_policy("audit_logs")
        assert policy.retention_days == 365
        assert policy.disposition_action == "archive"

    async def test_list_policies(self, retention_service):
        await retention_service.set_policy("audit_logs", 90, "delete")
        await retention_service.set_policy("governance", 2557, "archive")
        policies = await retention_service.list_policies()
        assert len(policies) == 2

    async def test_list_policies_empty(self, retention_service):
        assert await retention_service.list_policies() == []

    async def test_default_retention_periods(self, retention_service):
        """Test default retention per classification level."""
        await retention_service.set_policy("audit_logs", 90, "delete")
        policy = await retention_service.get_policy("audit_logs")
        assert policy.retention_days == 90


class TestLegalHold:
    async def test_impose_hold(self, retention_service):
        hold = await retention_service.impose_hold(
            record_types=["audit_logs", "lineage"],
            tenant_id="acme-corp",
            hold_ref="Litigation Case 2024-001",
            imposed_by="legal@acme.com",
        )
        assert hold.hold_id is not None
        assert hold.tenant_id == "acme-corp"
        assert hold.hold_ref == "Litigation Case 2024-001"
        assert hold.imposed_by == "legal@acme.com"
        assert hold.released_at is None

    async def test_list_holds(self, retention_service):
        await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref A", "admin@acme.com"
        )
        await retention_service.impose_hold(
            ["lineage"], "other-corp", "Ref B", "admin@acme.com"
        )
        holds = await retention_service.list_holds()
        assert len(holds) == 2

    async def test_list_holds_empty(self, retention_service):
        assert await retention_service.list_holds() == []

    async def test_is_hold_active_true(self, retention_service):
        await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref", "admin@acme.com"
        )
        assert (
            await retention_service.is_hold_active("audit_logs", "acme-corp") is True
        )

    async def test_is_hold_active_false_no_hold(self, retention_service):
        assert (
            await retention_service.is_hold_active("audit_logs", "acme-corp") is False
        )

    async def test_is_hold_active_wrong_tenant(self, retention_service):
        await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref", "admin@acme.com"
        )
        assert (
            await retention_service.is_hold_active("audit_logs", "other-corp") is False
        )

    async def test_is_hold_active_wrong_record_type(self, retention_service):
        await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref", "admin@acme.com"
        )
        assert (
            await retention_service.is_hold_active("lineage", "acme-corp") is False
        )

    async def test_release_hold(self, retention_service):
        hold = await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref", "admin@acme.com"
        )
        released = await retention_service.release_hold(
            hold.hold_id, released_by="legal@acme.com"
        )
        assert released.released_at is not None
        assert (
            await retention_service.is_hold_active("audit_logs", "acme-corp") is False
        )

    async def test_release_nonexistent_hold_raises(self, retention_service):
        with pytest.raises(ValueError, match="Hold not found"):
            await retention_service.release_hold("no-such", "admin@acme.com")

    async def test_hold_with_multiple_record_types(self, retention_service):
        await retention_service.impose_hold(
            ["audit_logs", "lineage", "governance"],
            "acme-corp",
            "Ref",
            "admin@acme.com",
        )
        assert (
            await retention_service.is_hold_active("audit_logs", "acme-corp") is True
        )
        assert (
            await retention_service.is_hold_active("lineage", "acme-corp") is True
        )
        assert (
            await retention_service.is_hold_active("governance", "acme-corp") is True
        )

    async def test_hold_with_filters(self, retention_service):
        hold = await retention_service.impose_hold(
            record_types=["audit_logs"],
            tenant_id="acme-corp",
            hold_ref="Ref",
            imposed_by="admin@acme.com",
            filters={"session_id": "ses-001"},
        )
        assert hold.filters == {"session_id": "ses-001"}

    async def test_released_hold_not_active(self, retention_service):
        hold = await retention_service.impose_hold(
            ["audit_logs"], "acme-corp", "Ref", "admin@acme.com"
        )
        await retention_service.release_hold(hold.hold_id, "legal@acme.com")
        assert (
            await retention_service.is_hold_active("audit_logs", "acme-corp") is False
        )
