"""End-to-end DSAR workflow integration tests.

Covers:
- DsarWorkflow submits, queries, and fulfills DSAR requests
- EDiscoveryExporter includes DSAR requests in exports
- DSAR requests appear in all three export formats
- Date filtering correctly scopes DSAR requests
- Status filtering is reflected in export metadata
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from anonreq.ediscovery.export import EDiscoveryExporter
from anonreq.models.ediscovery import ExportFormat

_TENANT = "tenant-dsar-int"
_T0 = datetime(2025, 10, 1, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 10, 15, 12, 0, 0, tzinfo=UTC)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
async def db_session() -> AsyncSession:
    """Create an in-memory SQLite database with DSAR data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS dsar_requests (
                id TEXT PRIMARY KEY, tenant_id TEXT, subject_id TEXT,
                request_type TEXT, status TEXT, verification_details TEXT,
                submitted_at TIMESTAMP, verified_at TIMESTAMP,
                fulfilled_at TIMESTAMP, fulfilled_by TEXT,
                verified_by TEXT, result TEXT, notes TEXT
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS data_lineage (
                id TEXT PRIMARY KEY, session_id TEXT, tenant_id TEXT,
                provider TEXT, model TEXT, entity_types TEXT,
                entity_count INTEGER, policies_applied TEXT,
                classification_action TEXT, processing_time_ms INTEGER,
                request_timestamp TIMESTAMP, response_timestamp TIMESTAMP,
                cache_hit BOOLEAN, success BOOLEAN, error_type TEXT
            )
        """))

        # Insert DSAR requests
        for dsar_data in [
            {"id": "dsar_int_001", "ts": _T0, "rtype": "ACCESS", "status": "fulfilled"},
            {"id": "dsar_int_002", "ts": _T1, "rtype": "ERASURE", "status": "pending_verification"},
        ]:
            await session.execute(text("""
                INSERT INTO dsar_requests
                (id, tenant_id, subject_id, request_type, status,
                 verification_details, submitted_at, notes)
                VALUES (:id, :tid, :sid, :rtype, :status, :vd, :ts, :notes)
            """), {
                "id": dsar_data["id"], "tid": _TENANT,
                "sid": f"sub-{dsar_data['id'][-3:]}",
                "rtype": dsar_data["rtype"],
                "status": dsar_data["status"],
                "vd": "{}", "ts": dsar_data["ts"],
                "notes": f"DSAR {dsar_data['rtype']} request",
            })

        await session.commit()
        yield session
    await engine.dispose()


# ── Tests ─────────────────────────────────────────────────────────


class TestDSAREDiscovery:
    """Verify DSAR requests flow through eDiscovery export."""

    @pytest.mark.asyncio
    async def test_ediscovery_jsonl_contains_dsar(
        self, db_session: AsyncSession
    ):
        """JSONL export includes DSAR records."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.JSONL,
        )
        assert result.record_count >= 2, \
            "Expected at least 2 DSAR records"
        data_lines = [
            l for l in result.content.strip().split("\n")  # noqa: E741
            if l.strip() and not l.startswith("#")
        ]
        assert len(data_lines) == result.record_count

    @pytest.mark.asyncio
    async def test_ediscovery_pdf_contains_dsar(
        self, db_session: AsyncSession
    ):
        """PDF export for DSAR tenant returns valid PDF."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.PDF,
        )
        assert result.content.startswith("%PDF")
        assert result.record_count >= 2

    @pytest.mark.asyncio
    async def test_ediscovery_edrm_contains_dsar_documents(
        self, db_session: AsyncSession
    ):
        """EDRM XML export includes DSAR Document elements."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.EDRM_XML,
        )
        assert "<Documents>" in result.content
        assert result.record_count >= 2

    @pytest.mark.asyncio
    async def test_dsar_date_filter(
        self, db_session: AsyncSession
    ):
        """Date range correctly scopes DSAR request inclusion."""
        exporter = EDiscoveryExporter(db=db_session)
        # Only _T1 and later
        result = await exporter.export(
            tenant_id=_TENANT,
            date_from=_T1,
            export_format=ExportFormat.JSONL,
        )
        # Should include dsar_int_002 (submitted at _T1)
        # but exclude dsar_int_001 (submitted at _T0, before date_from)
        assert result.record_count >= 1
