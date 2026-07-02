"""Tests for transparency service: session records, headers, conformity package.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.services.transparency import (
    TransparencyRecord,
    TransparencyService,
    add_transparency_headers,
)


@pytest.fixture
async def transparency_service(cache_manager):
    svc = TransparencyService(cache_manager)
    await svc._redis.delete("anonreq:transparency:sessions:acme-corp")
    yield svc


class TestTransparencyRecords:
    async def test_record_session(self, transparency_service):
        record = await transparency_service.record_session(
            tenant_id="acme-corp",
            session_id="sess_001",
            entity_count=5,
            entity_types=["EMAIL", "PHONE", "SSN"],
            anonymized=True,
        )
        assert record.session_id == "sess_001"
        assert record.entity_count == 5
        assert record.anonymized is True
        assert record.processed_at is not None

    async def test_get_session_record(self, transparency_service):
        await transparency_service.record_session(
            "acme-corp", "sess_001", 3, ["EMAIL"], True
        )
        fetched = await transparency_service.get_session_record("sess_001")
        assert fetched is not None
        assert fetched.session_id == "sess_001"
        assert fetched.entity_count == 3

    async def test_get_session_record_nonexistent(self, transparency_service):
        fetched = await transparency_service.get_session_record("no-such")
        assert fetched is None

    async def test_list_sessions_for_tenant(self, transparency_service):
        await transparency_service.record_session("acme-corp", "s1", 1, ["E1"], True)
        await transparency_service.record_session("acme-corp", "s2", 2, ["E2"], True)

        sessions = await transparency_service.list_sessions("acme-corp")
        assert len(sessions) == 2
        assert sessions[0].session_id == "s1"
        assert sessions[1].session_id == "s2"

    async def test_entity_count_aggregation(self, transparency_service):
        await transparency_service.record_session("acme-corp", "s1", 5, ["E1"], True)
        await transparency_service.record_session("acme-corp", "s2", 3, ["E2"], True)

        total = await transparency_service.get_total_entity_count("acme-corp")
        assert total == 8


class TestTransparencyHeaders:
    async def test_add_transparency_headers(self):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.headers = {}

        add_transparency_headers(response, processed=True, entity_count=7)
        assert response.headers.get("X-AnonReq-Processed") == "true"
        assert response.headers.get("X-AnonReq-Entity-Count") == "7"

    async def test_add_transparency_headers_zero_count(self):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.headers = {}

        add_transparency_headers(response, processed=True, entity_count=0)
        assert response.headers.get("X-AnonReq-Entity-Count") == "0"

    async def test_add_transparency_headers_not_processed(self):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.headers = {}

        add_transparency_headers(response, processed=False, entity_count=0)
        assert response.headers.get("X-AnonReq-Processed") == "false"


class TestConformityPackage:
    async def test_generate_conformity_package_returns_zip(self, transparency_service):
        zip_bytes = await transparency_service.generate_conformity_package("acme-corp")
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0
        assert zip_bytes[:4] == b"PK\x03\x04"

    async def test_conformity_package_contains_expected_sections(self, transparency_service):
        import zipfile
        import io

        zip_bytes = await transparency_service.generate_conformity_package("acme-corp")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "governance.json" in names
            assert "risk_assessments.json" in names
            assert "sbom.json" in names
            assert "config_audit.json" in names

    async def test_conformity_package_includes_tenant_data(self, transparency_service):
        await transparency_service.record_session("acme-corp", "s1", 5, ["EMAIL"], True)

        import zipfile
        import io

        zip_bytes = await transparency_service.generate_conformity_package("acme-corp")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            data = zf.read("transparency_records.json")
            import json
            records = json.loads(data)
            assert len(records) >= 1
            assert records[0]["session_id"] == "s1"

    async def test_conformity_package_empty_tenant(self, transparency_service):
        zip_bytes = await transparency_service.generate_conformity_package("empty-tenant")
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0
