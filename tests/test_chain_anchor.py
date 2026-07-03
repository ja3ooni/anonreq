"""Tests for ChainAnchorService with in-memory SQLite.

Uses aiosqlite with SQLAlchemy async engine for unit tests without
requiring PostgreSQL or MinIO.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime, timezone, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from anonreq.models.audit import AuditEvent, Base, DailyAnchor
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.chain_anchor import ChainAnchorService, AnchorConfig


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with full schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS audit_anchor ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "anchor_date TEXT NOT NULL, "
            "daily_root_hash TEXT NOT NULL, "
            "signature TEXT NOT NULL, "
            "event_count INTEGER NOT NULL, "
            "created_at TEXT NOT NULL"
            ")"
        ))
    yield engine
    await engine.dispose()


@pytest.fixture
async def audit_service(engine):
    """Create an AuditChainService for the test."""
    svc = AuditChainService(engine, AuditConfig(retention_days=2557))
    return svc


@pytest.fixture
async def anchor_service(engine, audit_service):
    """Create a ChainAnchorService with a test signing key."""
    config = AnchorConfig(
        signing_key="test-signing-key-for-unit-tests-123456",
    )
    svc = ChainAnchorService(audit_service, engine, config)
    return svc


def make_event(
    event_id: str,
    timestamp: datetime | None = None,
    tenant_id: str = "test_tenant",
    event_type: str = "test_event",
) -> AuditEvent:
    """Helper to create an AuditEvent with defaults."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return AuditEvent(
        event_id=event_id,
        prev_hash=None,
        hash="",
        timestamp=timestamp,
        tenant_id=tenant_id,
        request_id=f"req_{event_id}",
        policy_id=None,
        decision=None,
        provider=None,
        latency_ms=None,
        event_type=event_type,
        operator_id=None,
        change_type=None,
        prev_value_hash=None,
        new_value_hash=None,
        metadata_json=None,
        retention_days=2557,
    )


class TestDailyAnchorComputation:
    """Tests for the daily anchor computation logic."""

    async def test_compute_daily_anchor(self, anchor_service, audit_service):
        """Daily anchor is computed as SHA-384 of concatenated event hashes."""
        today = date.today()

        evt1 = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        evt2 = make_event("evt_002", timestamp=datetime(today.year, today.month, today.day, 13, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt1)
        await audit_service.store_event(evt2)

        anchor = await anchor_service.compute_daily_anchor(today)

        expected_root = hashlib.sha384((evt1.hash + evt2.hash).encode()).hexdigest()
        assert anchor.daily_root_hash == expected_root
        assert anchor.event_count == 2

    async def test_anchor_has_signature(self, anchor_service, audit_service):
        """Anchor is signed with HMAC-SHA384."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)

        anchor = await anchor_service.compute_daily_anchor(today)

        expected_sig = hmac.new(
            b"test-signing-key-for-unit-tests-123456",
            anchor.daily_root_hash.encode(),
            hashlib.sha384,
        ).hexdigest()
        assert anchor.signature == expected_sig

    async def test_anchor_no_events_raises(self, anchor_service):
        """Computing anchor for a date with no events raises ValueError."""
        with pytest.raises(ValueError, match="No events found"):
            await anchor_service.compute_daily_anchor(date(2020, 1, 1))

    async def test_anchor_empty_signature_without_key(self, engine, audit_service):
        """Without signing key, signature is empty string."""
        config = AnchorConfig(signing_key=None)
        svc = ChainAnchorService(audit_service, engine, config)
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)
        anchor = await svc.compute_daily_anchor(today)
        assert anchor.signature == ""


class TestAnchorStorage:
    """Tests for anchor storage and retrieval."""

    async def test_store_and_retrieve_anchor(self, anchor_service, audit_service, engine):
        """Stored anchor can be retrieved."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)
        anchor = await anchor_service.compute_daily_anchor(today)
        await anchor_service.store_anchor(anchor)

        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            result = await session.execute(
                text("SELECT anchor_date, daily_root_hash, signature, event_count FROM audit_anchor")
            )
            row = result.mappings().one()
            assert row["daily_root_hash"] == anchor.daily_root_hash
            assert row["event_count"] == 1


class TestAnchorVerification:
    """Tests for anchor verification."""

    async def test_verify_intact_anchor(self, anchor_service, audit_service):
        """Verification succeeds for an intact anchor."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)
        anchor = await anchor_service.compute_daily_anchor(today)
        await anchor_service.store_anchor(anchor)

        is_valid = await anchor_service.verify_anchor(today)
        assert is_valid

    async def test_verify_fails_tampered_events(self, anchor_service, audit_service, engine):
        """Verification fails when events have been tampered with."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)
        anchor = await anchor_service.compute_daily_anchor(today)
        await anchor_service.store_anchor(anchor)

        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            await session.execute(
                text("UPDATE audit_event SET hash = 'tampered' WHERE event_id = 'evt_001'")
            )
            await session.commit()

        is_valid = await anchor_service.verify_anchor(today)
        assert not is_valid

    async def test_verify_no_anchor_returns_false(self, anchor_service):
        """Verification returns False when no anchor exists."""
        is_valid = await anchor_service.verify_anchor(date(2020, 1, 1))
        assert not is_valid


class TestRunDailyAnchor:
    """Tests for the run_daily_anchor workflow."""

    async def test_run_daily_anchor_with_date(self, anchor_service, audit_service):
        """run_daily_anchor computes, signs, and stores in one call."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)

        anchor = await anchor_service.run_daily_anchor(today)
        assert anchor.anchor_date == today
        assert len(anchor.daily_root_hash) == 96
        assert anchor.event_count == 1

        is_valid = await anchor_service.verify_anchor(today)
        assert is_valid


class TestGetAnchorStatus:
    """Tests for get_anchor_status."""

    async def test_get_status_no_anchors(self, anchor_service):
        """Status returns empty info when no anchors exist."""
        status = await anchor_service.get_anchor_status()
        assert status["latest_anchor_date"] is None
        assert status["event_count"] == 0
        assert not status["is_verified"]

    async def test_get_status_with_anchor(self, anchor_service, audit_service):
        """Status returns anchor info when anchors exist."""
        today = date.today()
        evt = make_event("evt_001", timestamp=datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc))
        await audit_service.store_event(evt)
        await anchor_service.run_daily_anchor(today)

        status = await anchor_service.get_anchor_status()
        assert status["latest_anchor_date"] is not None
        assert status["event_count"] > 0
        assert status["is_verified"]
