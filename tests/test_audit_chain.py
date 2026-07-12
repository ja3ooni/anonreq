"""Tests for AuditChainService with in-memory SQLite.

Uses aiosqlite with SQLAlchemy async engine to run unit tests without
requiring PostgreSQL. The same schema is created in SQLite as the
PostgreSQL migration would create.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anonreq.models.audit import AuditEvent, Base, compute_event_hash
from anonreq.services.audit_chain import AuditChainService, AuditConfig


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with the audit schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def service(engine):
    """Create an AuditChainService with the test engine."""
    config = AuditConfig(retention_days=2557)
    svc = AuditChainService(engine, config)
    return svc


def make_event(
    event_id: str,
    tenant_id: str = "test_tenant",
    event_type: str = "test_event",
    prev_hash: str | None = None,
    timestamp: datetime | None = None,
) -> AuditEvent:
    """Helper to create an AuditEvent with defaults."""
    return AuditEvent(
        event_id=event_id,
        prev_hash=prev_hash,
        hash="",
        timestamp=timestamp or datetime.now(UTC),
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


class TestHashComputation:
    """Tests for the standalone hash computation function."""

    def test_sha384_hash_length(self):
        """SHA-384 hex digest is exactly 96 characters."""
        evt = make_event("evt_001")
        h = compute_event_hash(evt)
        assert len(h) == 96

    def test_hash_is_deterministic(self):
        """Same event fields produce the same hash."""
        ts = datetime.now(UTC)
        evt1 = make_event("evt_001", timestamp=ts)
        evt2 = make_event("evt_001", timestamp=ts)
        assert compute_event_hash(evt1) == compute_event_hash(evt2)

    def test_different_events_different_hash(self):
        """Different event IDs produce different hashes."""
        evt1 = make_event("evt_001")
        evt2 = make_event("evt_002")
        assert compute_event_hash(evt1) != compute_event_hash(evt2)

    def test_hash_excludes_hash_field(self):
        """The hash field is excluded from hash computation (no circularity)."""
        evt = make_event("evt_001")
        h1 = compute_event_hash(evt)
        evt.hash = h1
        h2 = compute_event_hash(evt)
        assert h1 == h2  # hash won't match because hash field is excluded


class TestAuditChainService:
    """Tests for AuditChainService with in-memory SQLite."""

    async def test_store_first_event(self, service):
        """First event gets prev_hash=None."""
        evt = make_event("evt_001")
        stored = await service.store_event(evt)
        assert stored.prev_hash is None
        assert len(stored.hash) == 96

    async def test_store_second_event_links_to_first(self, service):
        """Second event's prev_hash equals first event's hash."""
        evt1 = make_event("evt_001")
        await service.store_event(evt1)
        evt2 = make_event("evt_002")
        stored2 = await service.store_event(evt2)
        assert stored2.prev_hash == evt1.hash

    async def test_chain_of_three_events(self, service):
        """Three events form a correct linked chain."""
        evts = []
        for i in range(3):
            evt = make_event(f"evt_{i:03d}")
            stored = await service.store_event(evt)
            evts.append(stored)

        assert evts[0].prev_hash is None
        assert evts[1].prev_hash == evts[0].hash
        assert evts[2].prev_hash == evts[1].hash

    async def test_verify_chain_intact(self, service):
        """verify_chain returns is_intact=True for an intact chain."""
        for i in range(5):
            evt = make_event(f"evt_{i:03d}")
            await service.store_event(evt)

        result = await service.verify_chain("test_tenant")
        assert result.is_intact
        assert result.checked_count == 5
        assert result.broken_at is None

    async def test_verify_chain_detects_tampered_hash(self, service, engine):
        """verify_chain detects a modified hash."""
        for i in range(3):
            evt = make_event(f"evt_{i:03d}")
            await service.store_event(evt)

        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            await session.execute(
                text("UPDATE audit_event SET hash = 'tampered' WHERE event_id = 'evt_001'")
            )
            await session.commit()

        result = await service.verify_chain("test_tenant")
        assert not result.is_intact
        assert result.broken_at is not None

    async def test_verify_chain_detects_tampered_prev_hash(self, service, engine):
        """verify_chain detects a modified prev_hash."""
        for i in range(3):
            evt = make_event(f"evt_{i:03d}")
            await service.store_event(evt)

        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            await session.execute(
                text("UPDATE audit_event SET prev_hash = 'tampered' WHERE event_id = 'evt_001'")
            )
            await session.commit()

        result = await service.verify_chain("test_tenant")
        assert not result.is_intact

    async def test_append_only_no_update_method(self, service):
        """AuditChainService has no update or delete methods."""
        assert not hasattr(service, "update_event")
        assert not hasattr(service, "delete_event")

    async def test_append_only_no_delete_method(self, service):
        """Verify no mutable methods exist."""
        methods = [m for m in dir(service) if callable(getattr(service, m)) and not m.startswith("_")]  # noqa: E501
        mutable = {"update", "delete", "modify", "remove"}
        assert not mutable & set(methods)

    async def test_get_events_pagination(self, service):
        """get_events returns paginated results."""
        for i in range(10):
            evt = make_event(f"evt_{i:03d}")
            await service.store_event(evt)

        events = await service.get_events("test_tenant", limit=3)
        assert len(events) == 3

    async def test_get_events_filter_by_type(self, service):
        """get_events filters by event_type."""
        for i in range(3):
            evt = make_event(f"evt_config_{i:03d}", event_type="config_change")
            await service.store_event(evt)
        evt = make_event("evt_policy", event_type="policy_decision")
        await service.store_event(evt)

        events = await service.get_events("test_tenant", event_type="config_change")
        assert len(events) == 3

        events = await service.get_events("test_tenant", event_type="policy_decision")
        assert len(events) == 1

    async def test_concurrent_events_ordering(self, service):
        """Events stored sequentially maintain correct chain ordering."""
        for i in range(10):
            evt = make_event(f"evt_{i:03d}")
            await service.store_event(evt)

        result = await service.verify_chain("test_tenant")
        assert result.is_intact
        assert result.checked_count == 10

    async def test_store_event_with_existing_hash_raises(self, service):
        """Storing an event that already has a hash raises ValueError."""
        evt = make_event("evt_001")
        evt.hash = "already_set"
        with pytest.raises(ValueError, match="already has a hash"):
            await service.store_event(evt)

    async def test_verify_empty_chain(self, service):
        """verify_chain on empty chain returns intact."""
        result = await service.verify_chain("nonexistent")
        assert result.is_intact
        assert result.checked_count == 0

    async def test_get_latest_event(self, service):
        """get_latest_event returns the most recent event."""
        evt1 = make_event("evt_001")
        await service.store_event(evt1)
        evt2 = make_event("evt_002")
        await service.store_event(evt2)

        latest = await service.get_latest_event("test_tenant")
        assert latest is not None
        assert latest.event_id == "evt_002"
