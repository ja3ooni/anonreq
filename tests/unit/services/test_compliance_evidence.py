"""Unit tests for ComplianceEvidenceService."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from anonreq.services.compliance_evidence import ComplianceEvidenceService, EVIDENCE_STORAGE_DIR


class DummyCompliance:
    def __init__(self, compliant: bool):
        self.compliant = compliant


class DummyVerifyResult:
    def __init__(self, is_intact: bool, broken_at: str | None = None, checked_count: int = 42):
        self.is_intact = is_intact
        self.broken_at = broken_at
        self.checked_count = checked_count


@pytest.fixture
def mock_slo_engine():
    engine = MagicMock()
    # Mock get_all_compliance to return compliant values
    engine.get_all_compliance.return_value = {
        "latency": [DummyCompliance(True)],
        "availability": [DummyCompliance(True)],
    }
    return engine


@pytest.fixture
def mock_audit_chain():
    chain = MagicMock()
    chain.verify_chain.return_value = DummyVerifyResult(
        is_intact=True,
        broken_at=None,
        checked_count=100,
    )
    return chain


@pytest.mark.asyncio
async def test_collect_evidence_compliant(mock_slo_engine, mock_audit_chain):
    service = ComplianceEvidenceService(
        slo_engine=mock_slo_engine,
        audit_chain=mock_audit_chain,
    )

    evidence = await service.collect_evidence(framework="soc2", tenant_id="test-tenant")

    assert evidence["framework"] == "SOC2"
    assert evidence["tenant_id"] == "test-tenant"
    assert "collected_at" in evidence
    assert len(evidence["controls"]) == 2

    # Check SLO control
    slo_ctrl = next(c for c in evidence["controls"] if c["id"] == "slo_compliance")
    assert slo_ctrl["status"] == "compliant"
    assert slo_ctrl["source"] == "SLOEngine"

    # Check Audit control
    audit_ctrl = next(c for c in evidence["controls"] if c["id"] == "audit_chain_integrity")
    assert audit_ctrl["status"] == "compliant"
    assert audit_ctrl["evidence"]["is_intact"] is True
    assert audit_ctrl["evidence"]["checked_count"] == 100

    # Summary checks
    assert evidence["summary"]["total_controls"] == 2
    assert evidence["summary"]["compliant"] == 2
    assert evidence["summary"]["non_compliant"] == 0


@pytest.mark.asyncio
async def test_collect_evidence_non_compliant(mock_slo_engine, mock_audit_chain):
    # Set availability to non-compliant
    mock_slo_engine.get_all_compliance.return_value = {
        "latency": [DummyCompliance(True)],
        "availability": [DummyCompliance(False)],
    }
    mock_audit_chain.verify_chain.return_value = DummyVerifyResult(
        is_intact=False,
        broken_at="2026-07-07T12:00:00Z",
        checked_count=50,
    )

    service = ComplianceEvidenceService(
        slo_engine=mock_slo_engine,
        audit_chain=mock_audit_chain,
    )

    evidence = await service.collect_evidence(framework="iso27001", tenant_id="*")

    assert evidence["framework"] == "ISO27001"
    assert evidence["summary"]["compliant"] == 0
    assert evidence["summary"]["non_compliant"] == 2

    slo_ctrl = next(c for c in evidence["controls"] if c["id"] == "slo_compliance")
    assert slo_ctrl["status"] == "non_compliant"

    audit_ctrl = next(c for c in evidence["controls"] if c["id"] == "audit_chain_integrity")
    assert audit_ctrl["status"] == "non_compliant"
    assert audit_ctrl["evidence"]["is_intact"] is False
    assert audit_ctrl["evidence"]["broken_at"] == "2026-07-07T12:00:00Z"


@pytest.mark.asyncio
async def test_store_snapshot_filesystem(mock_slo_engine):
    service = ComplianceEvidenceService(
        slo_engine=mock_slo_engine,
    )

    evidence = await service.collect_evidence(framework="soc2", tenant_id="test-tenant")

    # The store_snapshot is automatically run in collect_evidence, but let's run it explicitly
    filepath = await service.store_snapshot(evidence)

    assert os.path.exists(filepath)
    assert filepath.endswith(".jsonl")

    # Read file and verify
    with open(filepath, "r", encoding="utf-8") as f:
        line = f.readline()
        loaded = json.loads(line)
        assert loaded["framework"] == "SOC2"
        assert loaded["tenant_id"] == "test-tenant"

    # Clean up the file
    os.remove(filepath)


@pytest.mark.asyncio
async def test_store_snapshot_minio():
    # Mock MinIO client
    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = False

    service = ComplianceEvidenceService(
        minio_client=mock_minio,
        bucket="test-compliance-bucket",
    )

    dummy_evidence = {
        "framework": "GDPR",
        "tenant_id": "eu-tenant",
        "controls": [],
    }

    result_path = await service.store_snapshot(dummy_evidence)

    assert result_path.startswith("minio://test-compliance-bucket/")
    mock_minio.bucket_exists.assert_called_once_with("test-compliance-bucket")
    mock_minio.make_bucket.assert_called_once_with("test-compliance-bucket")
    mock_minio.put_object.assert_called_once()
