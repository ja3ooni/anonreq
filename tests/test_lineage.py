"""Tests for immutable data lineage service.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.services.lineage import LineageRecord, LineageService


@pytest.fixture
async def lineage_service(cache_manager):
    svc = LineageService(cache_manager)
    keys = await svc._redis.keys("anonreq:lineage:*")
    for k in keys:
        await svc._redis.delete(k)
    yield svc


def sample_record(tenant_id="acme-corp", session_id="ses-001") -> LineageRecord:
    return LineageRecord(
        session_id=session_id,
        tenant_id=tenant_id,
        timestamp_request_received=datetime.now(timezone.utc),
        provider_routed_to="openai",
        model_used="gpt-4",
        entities_anonymized_count={"EMAIL": 2, "PHONE": 1},
        compliance_preset_applied="gdpr",
        classification_level_applied="Confidential",
        policy_actions_applied=["allow_and_anonymize"],
    )


class TestLineageRecordCreation:
    async def test_create_record_returns_record(self, lineage_service):
        record = sample_record()
        result = await lineage_service.create_record(record)
        assert result.session_id == "ses-001"
        assert result.tenant_id == "acme-corp"
        assert result.provider_routed_to == "openai"
        assert result.integrity_hash is not None
        assert len(result.integrity_hash) == 64  # SHA-256 hex

    async def test_create_record_stores_in_redis(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        raw = await lineage_service._redis.get("anonreq:lineage:ses-001")
        assert raw is not None

    async def test_create_record_adds_tenant_index(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        members = await lineage_service._redis.smembers(
            "anonreq:lineage:tenant:acme-corp"
        )
        assert b"ses-001" in members

    async def test_create_record_with_source_app_id(self, lineage_service):
        record = sample_record()
        record.source_application_id = "my-app-v1"
        result = await lineage_service.create_record(record)
        assert result.source_application_id == "my-app-v1"

    async def test_create_record_with_none_fields(self, lineage_service):
        record = LineageRecord(
            session_id="ses-min",
            tenant_id="acme-corp",
            timestamp_request_received=datetime.now(timezone.utc),
            entities_anonymized_count={},
            policy_actions_applied=[],
        )
        result = await lineage_service.create_record(record)
        assert result.provider_routed_to is None
        assert result.model_used is None
        assert result.compliance_preset_applied is None
        assert result.classification_level_applied is None


class TestLineageGetRecord:
    async def test_get_existing_record(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        fetched = await lineage_service.get_record("ses-001")
        assert fetched is not None
        assert fetched.session_id == "ses-001"
        assert fetched.provider_routed_to == "openai"

    async def test_get_nonexistent_record(self, lineage_service):
        fetched = await lineage_service.get_record("no-such")
        assert fetched is None

    async def test_get_record_has_all_fields(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        fetched = await lineage_service.get_record("ses-001")
        assert fetched.entities_anonymized_count == {"EMAIL": 2, "PHONE": 1}
        assert fetched.compliance_preset_applied == "gdpr"
        assert fetched.classification_level_applied == "Confidential"
        assert fetched.policy_actions_applied == ["allow_and_anonymize"]


class TestLineageListRecords:
    async def test_list_tenant_records(self, lineage_service):
        for i in range(3):
            r = sample_record(session_id=f"ses-{i:03d}")
            await lineage_service.create_record(r)
        records = await lineage_service.list_records("acme-corp")
        assert len(records) == 3

    async def test_list_empty_tenant(self, lineage_service):
        records = await lineage_service.list_records("no-such")
        assert records == []

    async def test_list_returns_records_in_order(self, lineage_service):
        record = sample_record(session_id="ses-001")
        await lineage_service.create_record(record)
        records = await lineage_service.list_records("acme-corp")
        assert records[0].session_id == "ses-001"


class TestLineageImmutability:
    async def test_no_modify_api_exists(self, lineage_service):
        svc_attrs = {k for k in dir(lineage_service) if not k.startswith("_")}
        bad = {"update_record", "delete_record", "modify_record", "patch_record"}
        assert len(svc_attrs & bad) == 0

    async def test_create_twice_same_session_overwrites(self, lineage_service):
        """Same session_id should be idempotent per the design."""
        r1 = sample_record()
        await lineage_service.create_record(r1)
        r2 = sample_record()
        r2.entities_anonymized_count = {"SSN": 1}
        await lineage_service.create_record(r2)
        fetched = await lineage_service.get_record("ses-001")
        assert fetched.entities_anonymized_count == {"SSN": 1}


class TestLineageIntegrity:
    async def test_verify_integrity_valid(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        assert await lineage_service.verify_integrity("ses-001") is True

    async def test_verify_integrity_nonexistent(self, lineage_service):
        assert await lineage_service.verify_integrity("no-such") is False

    async def test_verify_integrity_tampered(self, lineage_service):
        record = sample_record()
        await lineage_service.create_record(record)
        await lineage_service._redis.set(
            "anonreq:lineage:ses-001",
            '{"session_id":"ses-001","provider_routed_to":"evil"}',
        )
        assert await lineage_service.verify_integrity("ses-001") is False


class TestLineageCrossSession:
    async def test_multiple_tenants_isolated(self, lineage_service):
        r1 = sample_record(tenant_id="t1", session_id="s1")
        r2 = sample_record(tenant_id="t2", session_id="s2")
        await lineage_service.create_record(r1)
        await lineage_service.create_record(r2)
        assert len(await lineage_service.list_records("t1")) == 1
        assert len(await lineage_service.list_records("t2")) == 1
