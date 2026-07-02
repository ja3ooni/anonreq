"""Tests for human oversight service: approval queue, kill-switch, versioning.

Uses fakeredis-backed cache manager matching conftest patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.services.oversight import (
    ApprovalRequest,
    ApprovalRequestCreate,
    KillSwitchStatus,
    OversightService,
)


@pytest.fixture
async def oversight_service(cache_manager):
    svc = OversightService(cache_manager)
    # Ensure clean state
    await svc._redis.delete("anonreq:oversight:kill-switch")
    await svc._redis.delete("anonreq:oversight:approvals")
    yield svc


@pytest.fixture
async def seeded_approval(oversight_service) -> ApprovalRequest:
    req = await oversight_service.create_approval_request(
        tenant_id="acme-corp",
        request_type="high_risk",
        description="Anonymize financial PII for GPT-4",
        risk_score=0.85,
        metadata={"model": "gpt-4", "entities": ["SSN", "CC"]},
    )
    return req


class TestApprovalQueue:
    async def test_create_approval_request(self, oversight_service):
        req = await oversight_service.create_approval_request(
            tenant_id="acme-corp",
            request_type="high_risk",
            description="Test request",
            risk_score=0.75,
        )
        assert req.id is not None
        assert req.tenant_id == "acme-corp"
        assert req.status == "pending"
        assert req.risk_score == 0.75
        assert req.decided_by is None

    async def test_list_pending_approvals(self, oversight_service, seeded_approval):
        approvals = await oversight_service.list_pending_approvals()
        assert len(approvals) >= 1
        assert any(a.id == seeded_approval.id for a in approvals)

    async def test_list_pending_approvals_filters_tenant(self, oversight_service, seeded_approval):
        approvals = await oversight_service.list_pending_approvals(tenant_id="acme-corp")
        assert len(approvals) == 1
        assert approvals[0].tenant_id == "acme-corp"

        other = await oversight_service.list_pending_approvals(tenant_id="other")
        assert len(other) == 0

    async def test_approve_request(self, oversight_service, seeded_approval):
        approved = await oversight_service.approve_request(
            seeded_approval.id, operator_id="alice@acme.com"
        )
        assert approved.status == "approved"
        assert approved.decided_by == "alice@acme.com"
        assert approved.decided_at is not None

    async def test_reject_request(self, oversight_service, seeded_approval):
        rejected = await oversight_service.reject_request(
            seeded_approval.id, operator_id="bob@acme.com"
        )
        assert rejected.status == "rejected"
        assert rejected.decided_by == "bob@acme.com"
        assert rejected.decided_at is not None

    async def test_approve_nonexistent_raises(self, oversight_service):
        with pytest.raises(ValueError, match="not found"):
            await oversight_service.approve_request("no-such-id", "op")

    async def test_reject_nonexistent_raises(self, oversight_service):
        with pytest.raises(ValueError, match="not found"):
            await oversight_service.reject_request("no-such-id", "op")

    async def test_approve_already_decided_raises(self, oversight_service, seeded_approval):
        await oversight_service.approve_request(seeded_approval.id, "alice")
        with pytest.raises(ValueError, match="already"):
            await oversight_service.approve_request(seeded_approval.id, "bob")

    async def test_get_approval_request(self, oversight_service, seeded_approval):
        fetched = await oversight_service.get_approval_request(seeded_approval.id)
        assert fetched is not None
        assert fetched.id == seeded_approval.id

    async def test_get_approval_request_nonexistent(self, oversight_service):
        fetched = await oversight_service.get_approval_request("no-such")
        assert fetched is None


class TestKillSwitch:
    async def test_kill_switch_inactive_by_default(self, oversight_service):
        status = await oversight_service.get_kill_switch_status()
        assert status.active is False
        assert status.operator_id is None

    async def test_activate_kill_switch(self, oversight_service):
        await oversight_service.activate_kill_switch(
            operator_id="admin@acme.com",
            reason="Security incident detected",
        )
        status = await oversight_service.get_kill_switch_status()
        assert status.active is True
        assert status.operator_id == "admin@acme.com"
        assert status.reason == "Security incident detected"

    async def test_is_kill_switch_active(self, oversight_service):
        assert await oversight_service.is_kill_switch_active() is False
        await oversight_service.activate_kill_switch("admin", "test")
        assert await oversight_service.is_kill_switch_active() is True

    async def test_deactivate_kill_switch(self, oversight_service):
        await oversight_service.activate_kill_switch("admin", "test")
        await oversight_service.deactivate_kill_switch(operator_id="admin")
        status = await oversight_service.get_kill_switch_status()
        assert status.active is False

    async def test_activate_kill_switch_logs_timestamp(self, oversight_service):
        await oversight_service.activate_kill_switch("admin", "test")
        status = await oversight_service.get_kill_switch_status()
        assert status.activated_at is not None

    async def test_kill_switch_persists_metadata(self, oversight_service):
        await oversight_service.activate_kill_switch("admin", "emergency")
        status = await oversight_service.get_kill_switch_status()
        assert status.reason == "emergency"


class TestVersioning:
    async def test_governance_record_has_version(self):
        from anonreq.models.governance import GovernanceRecord, ReviewCycle, GovernanceOfficer, GovernanceOfficerRole
        from datetime import datetime

        record = GovernanceRecord(
            id=1,
            tenant_id="t1",
            officers=[
                GovernanceOfficer(
                    role=GovernanceOfficerRole.GOVERNANCE,
                    name="A", email="a@b.com"
                )
            ],
            review_cycle=ReviewCycle(
                id=1, tenant_id="t1", interval_days=90,
                last_review_date=None, next_review_date=None,
                status="active",
            ),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            version=1,
        )
        assert record.version == 1

    async def test_change_entry_model(self):
        from anonreq.models.governance import ChangeEntry
        from datetime import datetime

        entry = ChangeEntry(
            version=1,
            changed_at=datetime.now(timezone.utc),
            changed_by="alice@acme.com",
            description="Initial creation",
            changes={"officers": "added 4 officers"},
        )
        assert entry.version == 1
        assert entry.changed_by == "alice@acme.com"
        assert entry.changes["officers"] == "added 4 officers"

    async def test_change_entry_default_timestamp(self):
        from anonreq.models.governance import ChangeEntry

        entry = ChangeEntry(
            version=1,
            changed_by="test",
            description="test",
        )
        assert entry.changed_at is not None
