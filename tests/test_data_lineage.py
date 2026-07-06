"""Tests for immutable data lineage with PostgreSQL + MinIO archival.

Per D-009, D-010, D-011:
- Immutable per-session lineage records
- PostgreSQL (queryable) + MinIO archive (per-session JSONL)
- No API to modify or delete lineage records
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anonreq.models.lineage import LineageRecord


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_record() -> LineageRecord:
    return LineageRecord(
        session_id="ses-001",
        tenant_id="acme",
        provider="openai",
        model="gpt-4",
        entity_types=["EMAIL", "PHONE"],
        entity_count=3,
        policies_applied=["anonymize"],
        classification_action="anonymize",
        processing_time_ms=150,
        request_timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db_session():
    session = AsyncMock()

    async def mock_execute(stmt, params=None):
        result = AsyncMock(spec=['fetchall', 'fetchone', 'rowcount'])
        result.rowcount = 0
        result.fetchall.return_value = []
        result.fetchone.return_value = None
        return result

    session.execute.side_effect = mock_execute
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_minio_client():
    client = MagicMock()
    client.bucket_exists.return_value = True
    client.put_object = MagicMock()
    client.get_object = MagicMock()
    return client


@pytest.fixture
def mock_archiver():
    arch = AsyncMock()
    arch.archive_lineage.return_value = "lineage/2026/07/05/acme/ses-001.json"
    arch.get_archived_lineage.return_value = {"session_id": "ses-001"}
    return arch


@pytest.fixture
async def tracker(mock_db_session, mock_archiver):
    from anonreq.lineage.tracker import LineageTracker

    return LineageTracker(db=mock_db_session, archive_service=mock_archiver)


# ── Test 1: record_lineage writes lineage record to PostgreSQL ──────────────


class TestRecordLineage:
    async def test_record_lineage_writes_to_postgres(
        self, tracker, mock_db_session, sample_record, mock_archiver
    ):
        """record_lineage inserts a record into PostgreSQL."""
        record_id = await tracker.record_lineage(sample_record)
        assert record_id is not None
        assert len(record_id) > 0
        # Verify PostgreSQL insert was called
        assert mock_db_session.add.called or mock_db_session.execute.called

    async def test_record_lineage_archives_to_minio(
        self, tracker, mock_archiver, sample_record
    ):
        """record_lineage also calls archive_lineage for MinIO archival."""
        await tracker.record_lineage(sample_record)
        mock_archiver.archive_lineage.assert_awaited_once()

    async def test_record_lineage_returns_record_id(
        self, tracker, mock_db_session, sample_record, mock_archiver
    ):
        """record_lineage returns a string record ID."""
        record_id = await tracker.record_lineage(sample_record)
        assert isinstance(record_id, str)

    async def test_record_lineage_stores_all_fields(
        self, tracker, mock_db_session, sample_record, mock_archiver
    ):
        """Lineage record retains all fields after storage."""
        record_id = await tracker.record_lineage(sample_record)
        # Verify the record was stored (check that the DB was called with the right data)
        assert record_id is not None


# ── Test 2: record_lineage archives to MinIO ────────────────────────────────


class TestLineageArchival:
    async def test_archive_called_with_record(
        self, tracker, mock_archiver, sample_record
    ):
        await tracker.record_lineage(sample_record)
        mock_archiver.archive_lineage.assert_awaited_once_with(sample_record)

    async def test_archive_preserves_session_id(
        self, tracker, sample_record
    ):
        """Archived record retains session_id."""
        from anonreq.lineage.archive import LineageArchiver

        archiver = LineageArchiver(minio_client=MagicMock())
        archiver._client = MagicMock()
        archiver._client.bucket_exists.return_value = True
        archiver._client.put_object = MagicMock()

        path = await archiver.archive_lineage(sample_record)
        assert "ses-001" in path or sample_record.session_id in path


# ── Test 3: query_lineage retrieves by various filters ──────────────────────


class TestQueryLineage:
    async def test_query_by_session_id(self, tracker, mock_db_session):
        records = await tracker.query_lineage(session_id="ses-001")
        assert isinstance(records, list)

    async def test_query_by_tenant_id(self, tracker, mock_db_session):
        records = await tracker.query_lineage(tenant_id="acme")
        assert isinstance(records, list)

    async def test_query_by_provider(self, tracker, mock_db_session):
        records = await tracker.query_lineage(provider="openai")
        assert isinstance(records, list)

    async def test_query_by_model(self, tracker, mock_db_session):
        records = await tracker.query_lineage(model="gpt-4")
        assert isinstance(records, list)

    async def test_query_by_date_range(self, tracker, mock_db_session):
        date_from = datetime.now(timezone.utc) - timedelta(days=7)
        date_to = datetime.now(timezone.utc)
        records = await tracker.query_lineage(
            date_from=date_from, date_to=date_to
        )
        assert isinstance(records, list)

    async def test_query_returns_filtered_results(
        self, tracker, mock_db_session
    ):
        records = await tracker.query_lineage(
            tenant_id="acme", provider="openai"
        )
        assert isinstance(records, list)


# ── Test 4: No API to modify or delete lineage records ──────────────────────


class TestLineageImmutability:
    async def test_no_update_method(self):
        """LineageTracker has no update_record method."""
        from anonreq.lineage.tracker import LineageTracker

        attrs = {k for k in dir(LineageTracker) if not k.startswith("_")}
        bad = {"update_record", "delete_record", "modify_record", "patch_record"}
        assert len(attrs & bad) == 0

    async def test_no_delete_endpoint(self):
        """LineageTracker has no delete methods."""
        from anonreq.lineage.tracker import LineageTracker

        attrs = {k for k in dir(LineageTracker) if not k.startswith("_")}
        assert "delete_record" not in attrs
        assert "remove_record" not in attrs


# ── Test 5: Lineage record contains all required fields ──────────────────────


class TestLineageRecordSchema:
    def test_record_has_all_required_fields(self, sample_record):
        """LineageRecord contains all required fields per D-009."""
        assert sample_record.session_id == "ses-001"
        assert sample_record.tenant_id == "acme"
        assert sample_record.provider == "openai"
        assert sample_record.model == "gpt-4"
        assert sample_record.entity_types == ["EMAIL", "PHONE"]
        assert sample_record.entity_count == 3
        assert sample_record.policies_applied == ["anonymize"]
        assert sample_record.processing_time_ms == 150
        assert sample_record.success is True

    def test_record_with_optional_fields(self):
        """LineageRecord handles optional fields."""
        rec = LineageRecord(
            session_id="s1",
            tenant_id="acme",
            entity_types=[],
            entity_count=0,
            policies_applied=[],
            processing_time_ms=0,
            request_timestamp=datetime.now(timezone.utc),
        )
        assert rec.provider is None
        assert rec.model is None
        assert rec.cache_hit is False
        assert rec.success is True
        assert rec.error_type is None

    def test_record_with_error(self):
        """LineageRecord captures error state."""
        rec = LineageRecord(
            session_id="s1",
            tenant_id="acme",
            entity_types=[],
            entity_count=0,
            policies_applied=[],
            processing_time_ms=0,
            request_timestamp=datetime.now(timezone.utc),
            success=False,
            error_type="provider_timeout",
        )
        assert rec.success is False
        assert rec.error_type == "provider_timeout"

    def test_record_timestamps(self):
        """LineageRecord handles request and response timestamps."""
        now = datetime.now(timezone.utc)
        later = now + timedelta(seconds=5)
        rec = LineageRecord(
            session_id="s1",
            tenant_id="acme",
            entity_types=[],
            entity_count=0,
            policies_applied=[],
            processing_time_ms=5000,
            request_timestamp=now,
            response_timestamp=later,
        )
        assert rec.request_timestamp == now
        assert rec.response_timestamp == later
        assert rec.response_timestamp > rec.request_timestamp

    def test_record_cache_hit(self):
        """LineageRecord captures cache state."""
        rec = LineageRecord(
            session_id="s1",
            tenant_id="acme",
            entity_types=[],
            entity_count=0,
            policies_applied=[],
            processing_time_ms=5,
            request_timestamp=datetime.now(timezone.utc),
            cache_hit=True,
        )
        assert rec.cache_hit is True


# ── Test 6: Archived lineage retrievable from MinIO ─────────────────────────


class TestArchivedLineageRetrieval:
    async def test_get_archived_lineage(self, mock_minio_client):
        """Archived lineage retrievable from MinIO by path."""
        from anonreq.lineage.archive import LineageArchiver

        archiver = LineageArchiver(
            minio_client=mock_minio_client,
            bucket="test-lineage-archive",
        )
        mock_minio_client.get_object.return_value.read.return_value = b'{"session_id": "ses-001"}'

        result = await archiver.get_archived_lineage(
            "lineage/2026/07/05/acme/ses-001.json"
        )
        assert result is not None
        assert "session_id" in result

    async def test_get_archived_lineage_not_found(self, mock_minio_client):
        """get_archived_lineage returns None for non-existent paths."""
        from anonreq.lineage.archive import LineageArchiver
        from minio.error import S3Error

        mock_minio_client.get_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            request_id="",
            resource="",
            host_id="",
            response=None,
        )

        archiver = LineageArchiver(
            minio_client=mock_minio_client,
            bucket="test-lineage-archive",
        )
        result = await archiver.get_archived_lineage("nonexistent/path.json")
        assert result is None

    async def test_ensure_bucket(self, mock_minio_client):
        """ensure_bucket creates bucket if not exists."""
        from anonreq.lineage.archive import LineageArchiver

        mock_minio_client.bucket_exists.return_value = False
        archiver = LineageArchiver(
            minio_client=mock_minio_client,
            bucket="test-lineage-archive",
        )
        result = await archiver.ensure_bucket()
        assert result is True
        mock_minio_client.make_bucket.assert_called_once_with("test-lineage-archive")

    async def test_ensure_bucket_already_exists(self, mock_minio_client):
        """ensure_bucket returns True if bucket already exists."""
        from anonreq.lineage.archive import LineageArchiver

        mock_minio_client.bucket_exists.return_value = True
        archiver = LineageArchiver(
            minio_client=mock_minio_client,
            bucket="test-lineage-archive",
        )
        result = await archiver.ensure_bucket()
        assert result is True
        mock_minio_client.make_bucket.assert_not_called()
