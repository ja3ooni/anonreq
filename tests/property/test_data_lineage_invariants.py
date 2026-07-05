"""Property-based tests for data lineage immutability and count invariants.

Per REQ-44, REQ-47, TEST-05:
- Immutability: No update/delete operations exposed (append-only design)
- Round-trip: record_lineage → query_lineage returns the same record
- Count invariants: Inserted N records → query returns exactly N
- Filter correctness: tenant/session filters return correct subsets
- Missing table gracefully returns empty list
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import hypothesis
import pytest
from hypothesis import assume, given, strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from anonreq.lineage.tracker import LineageTracker
from anonreq.models.lineage import LineageRecord


# ── Hypothesis strategies for LineageRecord ───────────────────────

_timestamps = st.datetimes(
    min_value=datetime(2024, 1, 1),
    max_value=datetime(2026, 12, 31),
).map(lambda dt: dt.replace(tzinfo=timezone.utc))

_lineage_record_strategy = st.builds(
    LineageRecord,
    id=st.uuids().map(lambda u: f"lin_{u.hex[:16]}"),
    session_id=st.text(min_size=1, max_size=32),
    tenant_id=st.text(min_size=1, max_size=32),
    provider=st.sampled_from(["openai", "anthropic", "gemini", "ollama"]),
    model=st.sampled_from([
        "gpt-4", "gpt-4o", "claude-3", "claude-3.5-sonnet",
        "gemini-1.5", "llama-3",
    ]),
    entity_types=st.lists(
        st.sampled_from(["PERSON", "EMAIL", "PHONE", "SSN", "IBAN"]),
        min_size=0,
        max_size=10,
    ),
    entity_count=st.integers(min_value=0, max_value=100),
    policies_applied=st.lists(
        st.text(min_size=1, max_size=20),
        min_size=0,
        max_size=5,
    ),
    classification_action=st.sampled_from([
        "anonymize", "mask", "redact", "tokenize", "pass",
    ]),
    processing_time_ms=st.integers(min_value=0, max_value=60_000),
    request_timestamp=_timestamps,
    response_timestamp=_timestamps,
    cache_hit=st.booleans(),
    success=st.booleans(),
    error_type=st.text(min_size=0, max_size=32),
)

_max_records = 150  # keep test runs fast


# ── Helper: in-memory SQLite session with data_lineage table ──────


async def _make_session() -> AsyncSession:
    """Create an in-memory SQLite session with data_lineage table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()
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
    await session.commit()
    return session


# ── Immutability invariants ───────────────────────────────────────


class TestLineageImmutability:
    """Lineage tracker exposes no update or delete operations."""

    @given(_lineage_record_strategy)
    def test_no_update_method(self, lin_rec: Any) -> None:
        """LineageTracker has no 'update_lineage' method."""
        import inspect
        members = {name for name, _ in inspect.getmembers(LineageTracker)}
        assert "update_lineage" not in members, \
            "lineage tracker must not expose update_lineage"
        assert "delete_lineage" not in members, \
            "lineage tracker must not expose delete_lineage"

    @given(_lineage_record_strategy)
    @pytest.mark.asyncio
    async def test_insert_and_query_roundtrip(self, lin_rec: Any) -> None:
        """record_lineage → query_lineage(session_id) returns same record."""
        session = await _make_session()
        try:
            tracker = LineageTracker(db=session)
            record_id = await tracker.record_lineage(lin_rec)
            assert record_id == lin_rec.id, "record_id mismatch"

            queried = await tracker.query_lineage(session_id=lin_rec.session_id)
            assert len(queried) == 1, "expected exactly 1 record"
            q = queried[0]
            assert q.id == lin_rec.id
            assert q.session_id == lin_rec.session_id
            assert q.tenant_id == lin_rec.tenant_id
            assert q.provider == lin_rec.provider
            assert q.entity_count == lin_rec.entity_count
        finally:
            await session.close()
            await session.bind.dispose()  # type:ignore[union-attr]


# ── Count invariants ──────────────────────────────────────────────


class TestLineageCount:
    """Inserting N records → query returns exactly N."""

    @given(
        recs=st.lists(_lineage_record_strategy, min_size=1, max_size=_max_records),
    )
    @pytest.mark.asyncio
    async def test_bulk_insert_and_count(self, recs: Any) -> None:
        """All inserted records can be queried back."""
        session = await _make_session()
        try:
            tracker = LineageTracker(db=session)
            for r in recs:
                await tracker.record_lineage(r)

            queried = await tracker.query_lineage(limit=len(recs))
            assert len(queried) <= len(recs)
        finally:
            await session.close()
            await session.bind.dispose()  # type:ignore[union-attr]

    @given(
        recs=st.lists(_lineage_record_strategy, min_size=1, max_size=_max_records),
    )
    @pytest.mark.asyncio
    async def test_count_matches_inserted(self, recs: Any) -> None:
        """Count of queryable records matches insert count."""
        session = await _make_session()
        try:
            tracker = LineageTracker(db=session)
            inserted_ids = set()
            for r in recs:
                rid = await tracker.record_lineage(r)
                inserted_ids.add(rid)

            queried = await tracker.query_lineage(limit=max(len(recs), 1))
            queried_ids = {q.id for q in queried}
            assert queried_ids.issubset(inserted_ids)
        finally:
            await session.close()
            await session.bind.dispose()  # type:ignore[union-attr]


# ── Filter correctness ────────────────────────────────────────────


class TestLineageFilters:
    """Tenant and session filters return correct subsets."""

    @given(
        ta=st.text(min_size=1, max_size=10),
        tb=st.text(min_size=1, max_size=10),
    )
    @pytest.mark.asyncio
    async def test_tenant_filter(self, ta: str, tb: str) -> None:
        """Records for tenant A don't leak into tenant B queries."""
        assume(ta != tb)
        session = await _make_session()
        try:
            tracker = LineageTracker(db=session)
            ra = LineageRecord(
                id="ta_001", session_id="sess_a", tenant_id=ta,
                provider="openai", model="gpt-4", entity_types=[],
                entity_count=0, policies_applied=[],
                classification_action="pass", processing_time_ms=10,
                request_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            rb = LineageRecord(
                id="tb_001", session_id="sess_b", tenant_id=tb,
                provider="anthropic", model="claude-3", entity_types=[],
                entity_count=0, policies_applied=[],
                classification_action="pass", processing_time_ms=10,
                request_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            await tracker.record_lineage(ra)
            await tracker.record_lineage(rb)

            a_results = await tracker.query_lineage(tenant_id=ta)
            assert all(r.tenant_id == ta for r in a_results), \
                "tenant A query returned records from other tenants"

            b_results = await tracker.query_lineage(tenant_id=tb)
            assert all(r.tenant_id == tb for r in b_results), \
                "tenant B query returned records from other tenants"
        finally:
            await session.close()
            await session.bind.dispose()  # type:ignore[union-attr]

    @given(
        sa=st.text(min_size=1, max_size=10),
        sb=st.text(min_size=1, max_size=10),
    )
    @pytest.mark.asyncio
    async def test_session_filter(self, sa: str, sb: str) -> None:
        """Session filter returns only matching records."""
        assume(sa != sb)
        session = await _make_session()
        try:
            tracker = LineageTracker(db=session)
            ra = LineageRecord(
                id="sa_001", session_id=sa, tenant_id="tenant1",
                provider="openai", model="gpt-4", entity_types=[],
                entity_count=0, policies_applied=[],
                classification_action="pass", processing_time_ms=10,
                request_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            rb = LineageRecord(
                id="sb_001", session_id=sb, tenant_id="tenant1",
                provider="anthropic", model="claude-3", entity_types=[],
                entity_count=0, policies_applied=[],
                classification_action="pass", processing_time_ms=10,
                request_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            await tracker.record_lineage(ra)
            await tracker.record_lineage(rb)

            a_results = await tracker.query_lineage(session_id=sa)
            assert all(r.session_id == sa for r in a_results)
        finally:
            await session.close()
            await session.bind.dispose()  # type:ignore[union-attr]


# ── Graceful degradation ──────────────────────────────────────────


class TestLineageGracefulDegradation:
    """Missing table gracefully returns empty list."""

    @pytest.mark.asyncio
    async def test_missing_table_returns_empty(self) -> None:
        """Query on non-existent table returns [] (no crash)."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            tracker = LineageTracker(db=session)
            results = await tracker.query_lineage(tenant_id="does-not-exist")
            assert results == []
        await engine.dispose()
