"""Tests for DSAR workflow service.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import pytest

from anonreq.services.dsar import DSARRequest, DSARService


@pytest.fixture
async def dsar_service(cache_manager):
    svc = DSARService(cache_manager)
    keys = await svc._redis.keys("anonreq:dsar:*")
    for k in keys:
        await svc._redis.delete(k)
    yield svc


class TestDSARCreate:
    async def test_create_access_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        assert req.request_id is not None
        assert req.request_type == "access"
        assert req.tenant_id == "acme-corp"
        assert req.subject_id == "user-001"
        assert req.status == "pending"

    async def test_create_erasure_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="erasure",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        assert req.request_type == "erasure"

    async def test_create_rectification_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="rectification",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        assert req.request_type == "rectification"

    async def test_create_portability_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="portability",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        assert req.request_type == "portability"

    async def test_create_restriction_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="restriction",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        assert req.request_type == "restriction"

    async def test_invalid_request_type_raises(self, dsar_service):
        with pytest.raises(ValueError, match="Invalid request type"):
            await dsar_service.create_request(
                request_type="invalid",
                tenant_id="acme-corp",
                subject_id="user-001",
                requested_by="user@acme.com",
            )


class TestDSARGet:
    async def test_get_existing_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        fetched = await dsar_service.get_request(req.request_id)
        assert fetched is not None
        assert fetched.request_id == req.request_id
        assert fetched.status == "pending"

    async def test_get_nonexistent_request(self, dsar_service):
        fetched = await dsar_service.get_request("no-such")
        assert fetched is None


class TestDSARList:
    async def test_list_requests(self, dsar_service):
        for i in range(3):
            await dsar_service.create_request(
                request_type="access",
                tenant_id="acme-corp",
                subject_id=f"user-{i:03d}",
                requested_by="user@acme.com",
            )
        requests = await dsar_service.list_requests("acme-corp")
        assert len(requests) == 3

    async def test_list_empty(self, dsar_service):
        requests = await dsar_service.list_requests("no-such")
        assert requests == []

    async def test_list_tenant_isolation(self, dsar_service):
        await dsar_service.create_request(
            request_type="access", tenant_id="t1", subject_id="u1", requested_by="a"
        )
        await dsar_service.create_request(
            request_type="erasure", tenant_id="t2", subject_id="u2", requested_by="b"
        )
        assert len(await dsar_service.list_requests("t1")) == 1
        assert len(await dsar_service.list_requests("t2")) == 1


class TestDSARWorkflow:
    async def test_process_erasure(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="erasure",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        processed = await dsar_service.process_erasure(
            req.request_id, processed_by="admin@acme.com"
        )
        assert processed.status == "completed"
        assert processed.result == "deleted"
        assert processed.completed_at is not None

    async def test_process_erasure_nonexistent_raises(self, dsar_service):
        with pytest.raises(ValueError, match="DSAR request not found"):
            await dsar_service.process_erasure("no-such", "admin@acme.com")

    async def test_process_erasure_wrong_type_raises(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        with pytest.raises(ValueError, match="Cannot process erasure"):
            await dsar_service.process_erasure(req.request_id, "admin@acme.com")

    async def test_process_rectification(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="rectification",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        processed = await dsar_service.process_rectification(
            req.request_id, processed_by="admin@acme.com"
        )
        assert processed.status == "completed"

    async def test_process_portability(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="portability",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        processed = await dsar_service.process_portability(
            req.request_id, processed_by="admin@acme.com"
        )
        assert processed.status == "completed"

    async def test_process_restriction(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="restriction",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        processed = await dsar_service.process_restriction(
            req.request_id, processed_by="admin@acme.com"
        )
        assert processed.status == "completed"
        assert processed.result == "processing_restricted"

    async def test_process_restriction_with_hold(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="restriction",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        processed = await dsar_service.process_restriction(
            req.request_id, processed_by="admin@acme.com", legal_hold=True
        )
        assert processed.result == "legal_hold"

    async def test_reject_request(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        rejected = await dsar_service.reject_request(
            req.request_id, reason="insufficient_identification"
        )
        assert rejected.status == "rejected"
        assert rejected.result == "insufficient_identification"

    async def test_get_status(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        status = await dsar_service.get_status(req.request_id)
        assert status == "pending"

    async def test_audit_trail_tracked(self, dsar_service):
        req = await dsar_service.create_request(
            request_type="erasure",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        await dsar_service.process_erasure(req.request_id, "admin@acme.com")
        history = await dsar_service.get_audit_trail(req.request_id)
        assert len(history) >= 2
