"""Tests for eDiscovery export service.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone

import pytest

from anonreq.services.ediscovery import eDiscoveryService
from anonreq.services.lineage import LineageRecord, LineageService
from anonreq.services.dsar import DSARService
from anonreq.services.retention import RetentionService


@pytest.fixture
async def ediscovery_service(cache_manager):
    lineage = LineageService(cache_manager)
    dsar = DSARService(cache_manager)
    retention = RetentionService(cache_manager)
    svc = eDiscoveryService(
        lineage_service=lineage,
        dsar_service=dsar,
        retention_service=retention,
    )
    keys = await cache_manager._redis.keys("anonreq:*")
    for k in keys:
        await cache_manager._redis.delete(k)
    yield svc


class TesteDiscoverySearch:
    async def test_search_lineage(self, ediscovery_service):
        record = LineageRecord(
            session_id="ses-001",
            tenant_id="acme-corp",
            timestamp_request_received=datetime.now(timezone.utc),
            provider_routed_to="openai",
            model_used="gpt-4",
            entities_anonymized_count={"EMAIL": 2},
            compliance_preset_applied="gdpr",
            classification_level_applied="Confidential",
            policy_actions_applied=["allow_and_anonymize"],
        )
        await ediscovery_service._lineage.create_record(record)
        results = await ediscovery_service.search(
            tenant_id="acme-corp",
            record_types=["lineage"],
        )
        assert len(results["lineage"]) == 1
        assert results["lineage"][0]["session_id"] == "ses-001"

    async def test_search_dsar(self, ediscovery_service):
        req = await ediscovery_service._dsar.create_request(
            request_type="access",
            tenant_id="acme-corp",
            subject_id="user-001",
            requested_by="user@acme.com",
        )
        results = await ediscovery_service.search(
            tenant_id="acme-corp",
            record_types=["dsar"],
        )
        assert len(results["dsar"]) == 1

    async def test_search_all_types(self, ediscovery_service):
        await ediscovery_service._lineage.create_record(
            LineageRecord(
                session_id="ses-001",
                tenant_id="acme-corp",
                timestamp_request_received=datetime.now(timezone.utc),
                entities_anonymized_count={},
                policy_actions_applied=[],
            )
        )
        await ediscovery_service._dsar.create_request(
            request_type="access", tenant_id="acme-corp", subject_id="u1",
            requested_by="a",
        )
        results = await ediscovery_service.search(
            tenant_id="acme-corp",
            record_types=None,
        )
        assert "lineage" in results
        assert "dsar" in results
        assert "retention" in results

    async def test_search_with_date_filter(self, ediscovery_service):
        await ediscovery_service._lineage.create_record(
            LineageRecord(
                session_id="ses-001",
                tenant_id="acme-corp",
                timestamp_request_received=datetime.now(timezone.utc),
                entities_anonymized_count={},
                policy_actions_applied=[],
            )
        )
        results = await ediscovery_service.search(
            tenant_id="acme-corp",
            record_types=["lineage"],
            date_from=datetime.now(timezone.utc),
        )
        assert len(results["lineage"]) == 1


class TesteDiscoveryExport:
    async def test_export_json(self, ediscovery_service):
        await ediscovery_service._lineage.create_record(
            LineageRecord(
                session_id="ses-001",
                tenant_id="acme-corp",
                timestamp_request_received=datetime.now(timezone.utc),
                entities_anonymized_count={},
                policy_actions_applied=[],
            )
        )
        json_str = await ediscovery_service.export_json(
            tenant_id="acme-corp",
            record_types=["lineage"],
        )
        data = json.loads(json_str)
        assert "lineage" in data
        assert len(data["lineage"]) == 1

    async def test_export_csv(self, ediscovery_service):
        await ediscovery_service._lineage.create_record(
            LineageRecord(
                session_id="ses-001",
                tenant_id="acme-corp",
                timestamp_request_received=datetime.now(timezone.utc),
                provider_routed_to="openai",
                entities_anonymized_count={"EMAIL": 1},
                policy_actions_applied=[],
            )
        )
        csv_str = await ediscovery_service.export_csv(
            tenant_id="acme-corp",
            record_types=["lineage"],
        )
        assert "session_id" in csv_str
        assert "ses-001" in csv_str

    async def test_export_empty(self, ediscovery_service):
        json_str = await ediscovery_service.export_json(
            tenant_id="no-such",
        )
        data = json.loads(json_str)
        assert len(data.get("lineage", [])) == 0
