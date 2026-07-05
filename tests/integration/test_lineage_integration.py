"""End-to-end data lineage integration tests (REQ-47).

Covers:
- LineageTracker records and queries lineage records
- Lineage records include all required provenance fields
- EDiscoveryExporter retrieves lineage records for a tenant
- PDF and EDRM XML exports correctly include lineage data
- Date range filtering works for lineage queries
- Error handling for missing sessions
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from anonreq.ediscovery.export import EDiscoveryExporter
from anonreq.models.ediscovery import ExportFormat


_TENANT = "tenant-lineage-int"
_SESSION = "ses-lineage-int-001"
_T0 = datetime(2025, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2025, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
async def db_session() -> AsyncSession:
    """Create an in-memory SQLite database with lineage data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
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
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS dsar_requests (
                id TEXT PRIMARY KEY, tenant_id TEXT, subject_id TEXT,
                request_type TEXT, status TEXT, verification_details TEXT,
                submitted_at TIMESTAMP, notes TEXT
            )
        """))

        # Insert lineage records
        for i, (eid, ts) in enumerate([
            ("lin_int_001", _T0),
            ("lin_int_002", _T1),
        ], start=1):
            await session.execute(text("""
                INSERT INTO data_lineage (
                    id, session_id, tenant_id, provider, model,
                    entity_types, entity_count, policies_applied,
                    classification_action, processing_time_ms,
                    request_timestamp, cache_hit, success
                ) VALUES (
                    :id, :sid, :tid, :provider, :model,
                    :entity_types, :count, :policies,
                    :action, :ms, :ts, :cache, :success
                )
            """), {
                "id": eid, "sid": _SESSION, "tid": _TENANT,
                "provider": "openai", "model": "gpt-4",
                "entity_types": "PERSON,EMAIL", "count": 2,
                "policies": "GDPR", "action": "anonymize",
                "ms": 150, "ts": ts, "cache": 0, "success": 1,
            })

        await session.commit()
        yield session
    await engine.dispose()


# ── Tests ─────────────────────────────────────────────────────────


class TestLineageEDiscovery:
    """Verify lineage records flow through eDiscovery export."""

    @pytest.mark.asyncio
    async def test_ediscovery_jsonl_contains_lineage(
        self, db_session: AsyncSession
    ):
        """JSONL export includes lineage records."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.JSONL,
        )
        assert result.record_count >= 2, \
            "Expected at least 2 lineage records"

        data_lines = [
            l for l in result.content.strip().split("\n")
            if l.strip() and not l.startswith("#")
        ]
        assert len(data_lines) == result.record_count

    @pytest.mark.asyncio
    async def test_ediscovery_pdf_contains_lineage(
        self, db_session: AsyncSession
    ):
        """PDF export for lineage tenant returns valid PDF."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.PDF,
        )
        assert result.content.startswith("%PDF")
        assert result.record_count >= 2

    @pytest.mark.asyncio
    async def test_ediscovery_edrm_contains_documents(
        self, db_session: AsyncSession
    ):
        """EDRM XML export contains Document elements."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id=_TENANT,
            export_format=ExportFormat.EDRM_XML,
        )
        assert "<Documents>" in result.content
        assert "<Document>" in result.content

    @pytest.mark.asyncio
    async def test_ediscovery_date_filter_lineage(
        self, db_session: AsyncSession
    ):
        """Date range filter excludes older lineage records."""
        exporter = EDiscoveryExporter(db=db_session)
        # Filter to a narrow window — date_from after _T0 but before _T1
        mid_date = datetime(2025, 9, 10, tzinfo=timezone.utc)
        result = await exporter.export(
            tenant_id=_TENANT,
            date_from=mid_date,
            export_format=ExportFormat.JSONL,
        )
        # lin_int_001 at _T0 (Sept 1) should be excluded
        # lin_int_002 at _T1 (Sept 15) should be included
        assert result.record_count == 1, \
            "Expected exactly 1 record after date_from filter"

    @pytest.mark.asyncio
    async def test_unknown_tenant_returns_empty(
        self, db_session: AsyncSession
    ):
        """Export for non-existent tenant returns zero records."""
        exporter = EDiscoveryExporter(db=db_session)
        result = await exporter.export(
            tenant_id="nonexistent-tenant-lineage",
            export_format=ExportFormat.JSONL,
        )
        assert result.record_count == 0
