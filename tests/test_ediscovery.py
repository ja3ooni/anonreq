"""Tests for eDiscovery export engine (Task 1 of 16-04).

Covers:
- JSONL export format
- PDF summary export format
- EDRM XML export format
- Filtering by tenant_id, date range, entity types
- Pagination (skip/limit)
- Empty results handling
- Error handling (invalid tenant, connection error)
- Cross-format consistency (same data, different formats)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from anonreq.ediscovery.export import EDiscoveryExporter
from anonreq.models.ediscovery import ExportFormat


# ── Shared test data ───────────────────────────────────────────────

TENANT_A = "tenant-ediscovery-a"
TENANT_B = "tenant-ediscovery-b"
SESSION_1 = "ses_ediscovery_001"
SESSION_2 = "ses_ediscovery_002"
T0 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2025, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
T3 = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────

def _insert_lineage_sql() -> list[dict]:
    """Return SQL param dicts for test lineage records."""
    return [
        {
            "id": "lin_test_001", "session_id": SESSION_1,
            "tenant_id": TENANT_A, "provider": "openai",
            "model": "gpt-4", "entity_types": "PERSON,EMAIL",
            "entity_count": 2, "policies_applied": "GDPR",
            "classification_action": "anonymize",
            "processing_time_ms": 150, "request_timestamp": T2,
            "response_timestamp": None, "cache_hit": False,
            "success": True, "error_type": None,
        },
        {
            "id": "lin_test_002", "session_id": SESSION_1,
            "tenant_id": TENANT_A, "provider": "openai",
            "model": "gpt-4", "entity_types": "PHONE",
            "entity_count": 1, "policies_applied": "GDPR",
            "classification_action": "anonymize",
            "processing_time_ms": 200, "request_timestamp": T2,
            "response_timestamp": None, "cache_hit": False,
            "success": True, "error_type": None,
        },
        {
            "id": "lin_test_003", "session_id": SESSION_2,
            "tenant_id": TENANT_A, "provider": "anthropic",
            "model": "claude-3", "entity_types": "PERSON,EMAIL,PHONE",
            "entity_count": 3, "policies_applied": "GDPR,CCPA",
            "classification_action": "anonymize",
            "processing_time_ms": 320, "request_timestamp": T3,
            "response_timestamp": None, "cache_hit": True,
            "success": True, "error_type": None,
        },
        {
            "id": "lin_test_004", "session_id": "ses_other",
            "tenant_id": TENANT_B, "provider": "google",
            "model": "gemini", "entity_types": "EMAIL",
            "entity_count": 1, "policies_applied": "CCPA",
            "classification_action": "allow",
            "processing_time_ms": 50, "request_timestamp": T2,
            "response_timestamp": None, "cache_hit": False,
            "success": True, "error_type": None,
        },
        {
            "id": "lin_test_005", "session_id": "ses_fail",
            "tenant_id": TENANT_A, "provider": "openai",
            "model": "gpt-4", "entity_types": "PERSON",
            "entity_count": 1, "policies_applied": "GDPR",
            "classification_action": "anonymize",
            "processing_time_ms": 0, "request_timestamp": T0,
            "response_timestamp": None, "cache_hit": False,
            "success": False, "error_type": "rate_limit",
        },
    ]


def _insert_dsar_sql() -> list[dict]:
    """Return SQL param dicts for test DSAR requests."""
    return [
        {
            "id": "dsar_ed_001", "tenant_id": TENANT_A,
            "subject_id": "sub-101", "request_type": "ACCESS",
            "status": "fulfilled", "verification_details": "{}",
            "submitted_at": T2, "notes": "Q2 access request",
        },
        {
            "id": "dsar_ed_002", "tenant_id": TENANT_A,
            "subject_id": "sub-102", "request_type": "ERASURE",
            "status": "pending_verification", "verification_details": "{}",
            "submitted_at": T3, "notes": "Right to erasure",
        },
        {
            "id": "dsar_ed_003", "tenant_id": TENANT_B,
            "subject_id": "sub-201", "request_type": "ACCESS",
            "status": "fulfilled", "verification_details": "{}",
            "submitted_at": T2, "notes": "Tenant B access",
        },
    ]


def _insert_breach_notifications_sql() -> list[dict]:
    """Return SQL param dicts for test breach notifications."""
    return [
        {
            "id": "notif_ed_001", "breach_id": "br_001",
            "target_type": "regulator", "target_id": "reg-eea",
            "channel": "email", "template_id": "gdpr-eu",
            "rendered_subject": "Breach notification",
            "rendered_body": "A data breach occurred...",
            "status": "sent", "created_at": T2,
        },
        {
            "id": "notif_ed_002", "breach_id": "br_001",
            "target_type": "tenant", "target_id": TENANT_A,
            "channel": "email", "template_id": "gdpr-eu",
            "rendered_subject": "Your data incident",
            "rendered_body": "An incident affected your data...",
            "status": "sent", "created_at": T2,
        },
    ]


def _insert_retention_config_sql() -> list[dict]:
    """Return SQL param dicts for retention config (minimal)."""
    return []


# ── Database fixtures ──────────────────────────────────────────────


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite database with all needed tables.

    Uses a single connection for both DDL and session operations
    to avoid SQLite :memory: per-connection isolation.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )() as session:
        # Create tables inside the session's connection
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS data_lineage (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                tenant_id TEXT,
                provider TEXT,
                model TEXT,
                entity_types TEXT,
                entity_count INTEGER,
                policies_applied TEXT,
                classification_action TEXT,
                processing_time_ms INTEGER,
                request_timestamp TIMESTAMP,
                response_timestamp TIMESTAMP,
                cache_hit BOOLEAN,
                success BOOLEAN,
                error_type TEXT
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS dsar_requests (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                subject_id TEXT,
                request_type TEXT,
                status TEXT,
                verification_details TEXT,
                submitted_at TIMESTAMP,
                verified_at TIMESTAMP,
                fulfilled_at TIMESTAMP,
                fulfilled_by TEXT,
                verified_by TEXT,
                result TEXT,
                notes TEXT
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS breach_notifications (
                id TEXT PRIMARY KEY,
                breach_id TEXT,
                target_type TEXT,
                target_id TEXT,
                channel TEXT,
                template_id TEXT,
                rendered_subject TEXT,
                rendered_body TEXT,
                status TEXT,
                created_at TIMESTAMP
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS regulator_notification_queue (
                id TEXT PRIMARY KEY,
                regulator_id TEXT,
                notification_id TEXT,
                status TEXT,
                priority INTEGER,
                created_at TIMESTAMP
            )
        """))

        # Insert test data
        for row in _insert_lineage_sql():
            await session.execute(
                text("""
                    INSERT INTO data_lineage (
                        id, session_id, tenant_id, provider, model,
                        entity_types, entity_count, policies_applied,
                        classification_action, processing_time_ms,
                        request_timestamp, response_timestamp,
                        cache_hit, success, error_type
                    ) VALUES (
                        :id, :session_id, :tenant_id, :provider, :model,
                        :entity_types, :entity_count, :policies_applied,
                        :classification_action, :processing_time_ms,
                        :request_timestamp, :response_timestamp,
                        :cache_hit, :success, :error_type
                    )
                """),
                row,
            )
        for row in _insert_dsar_sql():
            await session.execute(
                text("""
                    INSERT INTO dsar_requests (
                        id, tenant_id, subject_id, request_type,
                        status, verification_details, submitted_at, notes
                    ) VALUES (
                        :id, :tenant_id, :subject_id, :request_type,
                        :status, :verification_details, :submitted_at, :notes
                    )
                """),
                row,
            )
        for row in _insert_breach_notifications_sql():
            await session.execute(
                text("""
                    INSERT INTO breach_notifications (
                        id, breach_id, target_type, target_id, channel,
                        template_id, rendered_subject, rendered_body,
                        status, created_at
                    ) VALUES (
                        :id, :breach_id, :target_type, :target_id, :channel,
                        :template_id, :rendered_subject, :rendered_body,
                        :status, :created_at
                    )
                """),
                row,
            )

        await session.commit()

        yield session

    await engine.dispose()


@pytest.fixture
async def exporter(db_session: AsyncSession) -> EDiscoveryExporter:
    """Create EDiscoveryExporter with in-memory DB session."""
    return EDiscoveryExporter(db=db_session)


# ── Format helpers ─────────────────────────────────────────────────


def _data_lines(content: str) -> list[str]:
    """Return non-comment lines from JSONL content."""
    return [
        l for l in content.strip().split("\n")
        if l.strip() and not l.startswith("#")
    ]


class TestExportFormats:
    """Verify each export format produces valid output."""

    @pytest.mark.asyncio
    async def test_export_jsonl_structure(
        self, exporter: EDiscoveryExporter, db_session: AsyncSession
    ):
        """JSONL export returns newline-delimited JSON records."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
        )
        assert result.format == ExportFormat.JSONL
        assert result.content_type == "application/jsonl"
        assert result.file_extension == ".jsonl"
        assert result.record_count > 0

        data_lines = _data_lines(result.content)
        assert len(data_lines) == result.record_count
        for line in data_lines:
            import json
            record = json.loads(line)
            assert "id" in record
            assert "source" in record

    @pytest.mark.asyncio
    async def test_export_pdf_structure(
        self, exporter: EDiscoveryExporter, db_session: AsyncSession
    ):
        """PDF export returns valid PDF bytes."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.PDF,
        )
        assert result.format == ExportFormat.PDF
        assert result.content_type == "application/pdf"
        assert result.file_extension == ".pdf"
        # PDF files start with %PDF
        assert result.content.startswith("%PDF")

    @pytest.mark.asyncio
    async def test_export_edrm_xml_structure(
        self, exporter: EDiscoveryExporter, db_session: AsyncSession
    ):
        """EDRM XML export returns valid XML."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.EDRM_XML,
        )
        assert result.format == ExportFormat.EDRM_XML
        assert result.content_type == "application/xml"
        assert result.file_extension == ".xml"
        assert "<?xml" in result.content
        assert "<EDRM>" in result.content or "<edrm" in result.content.lower()

    @pytest.mark.asyncio
    async def test_cross_format_record_count_consistency(
        self, exporter: EDiscoveryExporter, db_session: AsyncSession
    ):
        """All formats return same record count for same filters."""
        jsonl = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
        )
        pdf = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.PDF,
        )
        xml = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.EDRM_XML,
        )
        assert jsonl.record_count > 0
        assert jsonl.record_count == pdf.record_count
        assert pdf.record_count == xml.record_count


# ── Filtering ──────────────────────────────────────────────────────


class TestFiltering:
    """Verify export filtering by tenant, date, entity type."""

    @pytest.mark.asyncio
    async def test_filter_by_tenant_excludes_other(
        self, exporter: EDiscoveryExporter
    ):
        """Export for tenant A excludes tenant B records."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
        )
        data_lines = _data_lines(result.content)
        for line in data_lines:
            import json
            record = json.loads(line)
            src = record.get("source", {})
            tid = src.get("tenant_id", src.get("tenant", ""))
            assert tid == TENANT_A, f"Unexpected tenant: {tid}"

    @pytest.mark.asyncio
    async def test_filter_by_tenant_b_excludes_a(
        self, exporter: EDiscoveryExporter
    ):
        """Export for tenant B excludes tenant A records."""
        result = await exporter.export(
            tenant_id=TENANT_B,
            export_format=ExportFormat.JSONL,
        )
        data_lines = _data_lines(result.content)
        for line in data_lines:
            import json
            record = json.loads(line)
            src = record.get("source", {})
            tid = src.get("tenant_id", src.get("tenant", ""))
            assert tid == TENANT_B, f"Unexpected tenant: {tid}"

    @pytest.mark.asyncio
    async def test_filter_empty_tenant_returns_nothing(
        self, exporter: EDiscoveryExporter
    ):
        """Export for non-existent tenant returns empty result."""
        result = await exporter.export(
            tenant_id="nonexistent-tenant",
            export_format=ExportFormat.JSONL,
        )
        assert result.record_count == 0

    @pytest.mark.asyncio
    async def test_filter_by_date_range(
        self, exporter: EDiscoveryExporter
    ):
        """Export filtered to Q2 date range excludes oldest records."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            date_from=datetime(2025, 7, 1, tzinfo=timezone.utc),
            export_format=ExportFormat.JSONL,
        )
        # Should exclude lin_test_005 (T0 = June 1) and include July records
        data_lines = _data_lines(result.content)
        for line in data_lines:
            import json
            record = json.loads(line)
            ts = record.get("source", {}).get("request_timestamp", "")
            assert ts >= "2025-07-01" or not ts, \
                f"Record before date range: {ts}"

    @pytest.mark.asyncio
    async def test_filter_date_range_both_bounds(
        self, exporter: EDiscoveryExporter
    ):
        """Export with both date_from and date_to."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            date_from=datetime(2025, 6, 1, tzinfo=timezone.utc),
            date_to=datetime(2025, 6, 30, tzinfo=timezone.utc),
            export_format=ExportFormat.JSONL,
        )
        # Only lin_test_005 (T0 = June 1) falls in this range
        assert result.record_count >= 1


# ── Pagination ─────────────────────────────────────────────────────


class TestPagination:
    """Verify skip/limit pagination works."""

    @pytest.mark.asyncio
    async def test_pagination_limit(
        self, exporter: EDiscoveryExporter
    ):
        """Export with limit returns at most N records."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
            limit=2,
        )
        assert result.record_count <= 2

    @pytest.mark.asyncio
    async def test_pagination_skip(
        self, exporter: EDiscoveryExporter
    ):
        """Export with skip >= total returns empty."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
            skip=100,
        )
        assert result.record_count == 0

    @pytest.mark.asyncio
    async def test_pagination_first_page_has_items(
        self, exporter: EDiscoveryExporter
    ):
        """Export page 1 has items when data exists."""
        result = await exporter.export(
            tenant_id=TENANT_A,
            export_format=ExportFormat.JSONL,
            skip=0,
            limit=2,
        )
        assert result.record_count > 0


# ── Error handling ─────────────────────────────────────────────────


class TestErrorHandling:
    """Verify exporter handles edge cases gracefully."""

    @pytest.mark.asyncio
    async def test_exporter_rejects_invalid_format(
        self, exporter: EDiscoveryExporter
    ):
        """Export raises ValueError for unknown format."""
        import anonreq.models.ediscovery as edm

        class FakeFormat:
            value = "unknown"

        with pytest.raises(ValueError, match="Unsupported export format"):
            await exporter.export(
                tenant_id=TENANT_A,
                export_format=FakeFormat(),  # type: ignore[arg-type]
            )

    @pytest.mark.asyncio
    async def test_exporter_handles_db_empty(
        self, db_session: AsyncSession
    ):
        """Export on fresh (empty) DB returns empty."""
        # Drop all data and recreate exporter with clean session
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    id TEXT PRIMARY KEY, session_id TEXT,
                    tenant_id TEXT, provider TEXT, model TEXT,
                    entity_types TEXT, entity_count INTEGER,
                    policies_applied TEXT, classification_action TEXT,
                    processing_time_ms INTEGER,
                    request_timestamp TIMESTAMP,
                    response_timestamp TIMESTAMP,
                    cache_hit BOOLEAN, success BOOLEAN, error_type TEXT
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dsar_requests (
                    id TEXT PRIMARY KEY, tenant_id TEXT,
                    subject_id TEXT, request_type TEXT, status TEXT,
                    verification_details TEXT, submitted_at TIMESTAMP,
                    notes TEXT
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS breach_notifications (
                    id TEXT PRIMARY KEY, breach_id TEXT,
                    target_type TEXT, target_id TEXT, channel TEXT,
                    template_id TEXT, rendered_subject TEXT,
                    rendered_body TEXT, status TEXT, created_at TIMESTAMP
                )
            """))

        async with sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )() as session:
            exp = EDiscoveryExporter(db=session)
            result = await exp.export(
                tenant_id=TENANT_A,
                export_format=ExportFormat.JSONL,
            )
            assert result.record_count == 0

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_exporter_file_extension_matches_format(
        self, exporter: EDiscoveryExporter
    ):
        """Each format produces correct file extension."""
        for fmt, ext in [
            (ExportFormat.JSONL, ".jsonl"),
            (ExportFormat.PDF, ".pdf"),
            (ExportFormat.EDRM_XML, ".xml"),
        ]:
            result = await exporter.export(
                tenant_id=TENANT_A,
                export_format=fmt,
            )
            assert result.filename.endswith(ext), \
                f"{fmt}: expected {ext}, got {result.filename}"
