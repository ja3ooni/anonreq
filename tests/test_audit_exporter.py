"""Unit tests for AuditExporter."""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
import pyarrow.parquet as pq
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.models.audit import AuditEvent, Base
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.audit_exporter import AuditExporter, ExportConfig, MinioConfig, MonthlyConfig


@pytest.fixture
async def audit_engine():
    """Create an in-memory SQLite engine with the audit schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def audit_chain(audit_engine):
    config = AuditConfig(retention_days=2557)
    return AuditChainService(audit_engine, config)


@pytest.mark.asyncio
async def test_audit_exporter_generates_files_and_uploads(audit_chain):
    # Setup some test events
    # Event 1: in July 2026
    # Event 2: in August 2026
    # Event 3: in July 2026
    e1 = AuditEvent(
        event_id="e1", prev_hash=None, hash="",
        timestamp=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
        tenant_id="tenant1", request_id=None, policy_id=None, decision=None,
        provider=None, latency_ms=None, event_type="config_change",
        operator_id="op1", change_type="update", prev_value_hash=None,
        new_value_hash=None, metadata_json=None
    )
    e2 = AuditEvent(
        event_id="e2", prev_hash="h1", hash="",
        timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        tenant_id="tenant1", request_id=None, policy_id=None, decision=None,
        provider=None, latency_ms=None, event_type="config_change",
        operator_id="op1", change_type="update", prev_value_hash=None,
        new_value_hash=None, metadata_json=None
    )
    e3 = AuditEvent(
        event_id="e3", prev_hash="h2", hash="",
        timestamp=datetime(2026, 7, 30, 23, 59, 59, tzinfo=timezone.utc),
        tenant_id="tenant2", request_id=None, policy_id=None, decision=None,
        provider=None, latency_ms=None, event_type="slo_breach_detected",
        operator_id=None, change_type=None, prev_value_hash=None,
        new_value_hash=None, metadata_json=None
    )

    await audit_chain.store_event(e1)
    await audit_chain.store_event(e2)
    await audit_chain.store_event(e3)

    # Initialize exporter
    cfg = ExportConfig(
        monthly=MonthlyConfig(enabled=True, schedule="0 0 5 * *", formats=["jsonl", "parquet"], compression="gzip"),
        minio=MinioConfig(endpoint="http://localhost:9000", bucket="test-bucket", access_key="key", secret_key="secret", secure=False, worm_enabled=True, retention_days=30)
    )
    
    exporter = AuditExporter(audit_chain, config=cfg)

    # Mock MinIO client
    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    
    # Track files uploaded
    uploaded_files = {}
    
    def mock_fput_object(bucket_name, remote_path, local_path):
        # Read file contents and save
        with open(local_path, "rb") as f:
            uploaded_files[remote_path] = f.read()
            
    mock_minio.fput_object.side_effect = mock_fput_object

    with patch.object(exporter, "_get_minio_client", return_value=mock_minio):
        result = await exporter.export_month(2026, 7)

        # 2 events from July should be exported
        assert result.event_count == 2
        assert "jsonl" in result.formats
        assert "parquet" in result.formats
        assert "jsonl" in result.checksums
        assert "parquet" in result.checksums

        # Verify MinIO calls
        assert mock_minio.fput_object.call_count == 2
        assert "exports/audit-2026-07.jsonl.gz" in uploaded_files
        assert "exports/audit-2026-07.parquet" in uploaded_files

        # Verify JSONL content: only July events e1 and e3
        jsonl_data = gzip.decompress(uploaded_files["exports/audit-2026-07.jsonl.gz"]).decode()
        lines = [json.loads(line) for line in jsonl_data.strip().split("\n") if line]
        assert len(lines) == 2
        event_ids = {line["event_id"] for line in lines}
        assert event_ids == {"e1", "e3"}

        # Verify Parquet content
        temp_parquet_path = "temp_test.parquet"
        with open(temp_parquet_path, "wb") as f:
            f.write(uploaded_files["exports/audit-2026-07.parquet"])
        try:
            pq_table = pq.read_table(temp_parquet_path)
            assert pq_table.num_rows == 2
            assert "event_id" in pq_table.column_names
            assert set(pq_table.column("event_id").to_pylist()) == {"e1", "e3"}
        finally:
            if os.path.exists(temp_parquet_path):
                os.remove(temp_parquet_path)

        # Verify tracking entry in DB
        async with audit_chain._session_factory() as session:
            db_res = await session.execute(text("SELECT * FROM export_tracking"))
            rows = db_res.mappings().all()
            assert len(rows) == 1
            assert rows[0]["year"] == 2026
            assert rows[0]["month"] == 7
            assert rows[0]["event_count"] == 2


@pytest.mark.asyncio
async def test_audit_exporter_empty_month(audit_chain):
    cfg = ExportConfig(
        monthly=MonthlyConfig(enabled=True, schedule="0 0 5 * *", formats=["jsonl", "parquet"], compression="gzip"),
        minio=MinioConfig(endpoint="http://localhost:9000", bucket="test-bucket", access_key="key", secret_key="secret", secure=False, worm_enabled=True, retention_days=30)
    )
    exporter = AuditExporter(audit_chain, config=cfg)

    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    uploaded_files = {}
    
    def mock_fput_object(bucket_name, remote_path, local_path):
        with open(local_path, "rb") as f:
            uploaded_files[remote_path] = f.read()
    mock_minio.fput_object.side_effect = mock_fput_object

    with patch.object(exporter, "_get_minio_client", return_value=mock_minio):
        result = await exporter.export_month(2026, 12)
        assert result.event_count == 0

        # JSONL should be empty gzipped file
        jsonl_data = gzip.decompress(uploaded_files["exports/audit-2026-12.jsonl.gz"]).decode()
        assert jsonl_data == ""

        # Parquet should be a valid parquet table with 0 rows
        temp_parquet_path = "temp_empty.parquet"
        with open(temp_parquet_path, "wb") as f:
            f.write(uploaded_files["exports/audit-2026-12.parquet"])
        try:
            pq_table = pq.read_table(temp_parquet_path)
            assert pq_table.num_rows == 0
        finally:
            if os.path.exists(temp_parquet_path):
                os.remove(temp_parquet_path)
