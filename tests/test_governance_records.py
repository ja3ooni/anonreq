"""Tests for governance record CRUD, review cycles, and status endpoints.

Uses SQLite in-memory with aiosqlite matching Phase 11 test patterns.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from anonreq.models.audit import Base
from anonreq.models.governance import (
    GovernanceOfficer,
    GovernanceOfficerRole,
    GovernanceRecord,
    ReviewCycle,
    ReviewCycleModel,
    GovernanceRecordModel,
    RiskAssessmentModel,
    json_to_officers,
    officers_to_json,
)
from anonreq.governance.records import (
    create_governance_record,
    get_governance_record,
    list_governance_records,
    update_governance_record,
)
from anonreq.governance.reviews import (
    complete_review,
    count_records,
    get_overdue_reviews,
    get_upcoming_reviews,
    schedule_review,
)


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    """Create an async session bound to the test engine."""
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as s:
        yield s


def sample_officers() -> list[GovernanceOfficer]:
    return [
        GovernanceOfficer(
            role=GovernanceOfficerRole.GOVERNANCE,
            name="Alice",
            email="alice@acme.com",
        ),
        GovernanceOfficer(
            role=GovernanceOfficerRole.RISK,
            name="Bob",
            email="bob@acme.com",
        ),
        GovernanceOfficer(
            role=GovernanceOfficerRole.COMPLIANCE,
            name="Carol",
            email="carol@acme.com",
        ),
        GovernanceOfficer(
            role=GovernanceOfficerRole.SECURITY,
            name="Dave",
            email="dave@acme.com",
        ),
    ]


class TestGovernanceRecordCRUD:
    """Tests for governance record create, read, update, list."""

    async def test_create_governance_record_stores_all_owner_fields(
        self, session: AsyncSession
    ):
        """Test 1: create_governance_record stores record with all 4 owner fields."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )

        assert record.id > 0
        assert record.tenant_id == "acme-corp"
        assert len(record.officers) == 4
        assert record.officers[0].role == GovernanceOfficerRole.GOVERNANCE
        assert record.officers[1].role == GovernanceOfficerRole.RISK
        assert record.officers[2].role == GovernanceOfficerRole.COMPLIANCE
        assert record.officers[3].role == GovernanceOfficerRole.SECURITY
        assert record.review_cycle.interval_days == 90
        assert record.review_cycle.status == "active"
        assert record.status == "active"

    async def test_get_governance_record_returns_by_tenant_id(
        self, session: AsyncSession
    ):
        """Test 2: get_governance_record returns record by tenant_id."""
        officers = sample_officers()
        await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )

        fetched = await get_governance_record(session, "acme-corp")
        assert fetched is not None
        assert fetched.tenant_id == "acme-corp"
        assert len(fetched.officers) == 4

        missing = await get_governance_record(session, "nonexistent")
        assert missing is None

    async def test_update_governance_record_modifies_officers(
        self, session: AsyncSession
    ):
        """Test 3: update_governance_record modifies owners and updates updated_at."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )
        original_updated_at = record.updated_at

        new_officers = [
            GovernanceOfficer(
                role=GovernanceOfficerRole.GOVERNANCE,
                name="Eve",
                email="eve@acme.com",
            ),
            GovernanceOfficer(
                role=GovernanceOfficerRole.RISK,
                name="Frank",
                email="frank@acme.com",
            ),
            GovernanceOfficer(
                role=GovernanceOfficerRole.COMPLIANCE,
                name="Grace",
                email="grace@acme.com",
            ),
            GovernanceOfficer(
                role=GovernanceOfficerRole.SECURITY,
                name="Hank",
                email="hank@acme.com",
            ),
        ]

        updated = await update_governance_record(
            session, "acme-corp", new_officers
        )
        assert updated.officers[0].name == "Eve"
        assert updated.officers[1].name == "Frank"
        assert updated.updated_at > original_updated_at
        assert updated.tenant_id == "acme-corp"

    async def test_list_governance_records_paginates(
        self, session: AsyncSession
    ):
        """Test 4: list_governance_records paginates correctly."""
        for i in range(5):
            await create_governance_record(
                session,
                tenant_id=f"tenant_{i:03d}",
                officers=sample_officers(),
            )

        page1 = await list_governance_records(session, skip=0, limit=2)
        assert len(page1) == 2

        page2 = await list_governance_records(session, skip=2, limit=2)
        assert len(page2) == 2

        all_records = await list_governance_records(session, skip=0, limit=10)
        assert len(all_records) == 5

    async def test_update_nonexistent_record_raises(
        self, session: AsyncSession
    ):
        """Updating a non-existent record raises ValueError."""
        with pytest.raises(ValueError, match="No governance record"):
            await update_governance_record(session, "ghost", sample_officers())


class TestReviewCycles:
    """Tests for review cycle scheduling, overdue detection, completion."""

    async def test_review_cycle_default_90_day_interval(
        self, session: AsyncSession
    ):
        """Test 8: Review cycle scheduling sets default 90-day interval."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers, interval_days=90
        )
        assert record.review_cycle.interval_days == 90

        custom = await create_governance_record(
            session,
            tenant_id="other-corp",
            officers=officers,
            interval_days=30,
        )
        assert custom.review_cycle.interval_days == 30

    async def test_overdue_review_surfaced(
        self, session: AsyncSession
    ):
        """Test 7: Review cycle with past next_review_date surfaces as overdue."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )

        overdue = await get_overdue_reviews(session)
        assert len(overdue) == 0

        rc_id = record.review_cycle.id
        past_date = datetime.now(timezone.utc) - timedelta(days=10)
        await session.execute(
            text(
                "UPDATE review_cycle SET next_review_date = :dt WHERE id = :id"
            ),
            {"dt": past_date, "id": rc_id},
        )
        await session.commit()

        overdue = await get_overdue_reviews(session)
        assert len(overdue) == 1
        assert overdue[0].tenant_id == "acme-corp"

    async def test_upcoming_reviews_query(self, session: AsyncSession):
        """Upcoming reviews within 30 days are found."""
        officers = sample_officers()
        await create_governance_record(
            session,
            tenant_id="acme-corp",
            officers=officers,
            interval_days=5,
        )

        upcoming = await get_upcoming_reviews(session, days=30)
        assert len(upcoming) >= 1

    async def test_complete_review_updates_dates(self, session: AsyncSession):
        """Completing a review sets last_review_date and advances next_review."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )
        assert record.review_cycle.last_review_date is None

        cycle = await complete_review(session, "acme-corp")
        assert cycle.last_review_date is not None
        assert cycle.next_review_date is not None
        assert cycle.next_review_date > cycle.last_review_date

    async def test_complete_review_nonexistent_raises(
        self, session: AsyncSession
    ):
        """Complete review on non-existent tenant raises ValueError."""
        with pytest.raises(ValueError, match="No review cycle"):
            await complete_review(session, "ghost")

    async def test_schedule_review_creates_cycle(self, session: AsyncSession):
        """schedule_review creates a new review cycle."""
        cycle = await schedule_review(session, "new-tenant", interval_days=45)
        assert cycle.interval_days == 45
        assert cycle.tenant_id == "new-tenant"
        assert cycle.status == "active"

    async def test_schedule_review_updates_existing(self, session: AsyncSession):
        """schedule_review updates an existing cycle."""
        cycle1 = await schedule_review(session, "tenant-x", interval_days=90)
        cycle2 = await schedule_review(session, "tenant-x", interval_days=60)
        assert cycle2.id == cycle1.id
        assert cycle2.interval_days == 60

    async def test_count_records(self, session: AsyncSession):
        """count_records returns correct total."""
        assert await count_records(session) == 0

        officers = sample_officers()
        await create_governance_record(
            session, tenant_id="t1", officers=officers
        )
        await create_governance_record(
            session, tenant_id="t2", officers=officers
        )
        assert await count_records(session) == 2


class TestGovernanceStatus:
    """Tests for the governance status aggregator."""

    async def test_status_with_overdue_count(
        self, session: AsyncSession
    ):
        """Status reflects overdue review count."""
        officers = sample_officers()
        record = await create_governance_record(
            session, tenant_id="acme-corp", officers=officers
        )

        rc_id = record.review_cycle.id
        past_date = datetime.now(timezone.utc) - timedelta(days=15)
        await session.execute(
            text(
                "UPDATE review_cycle SET next_review_date = :dt WHERE id = :id"
            ),
            {"dt": past_date, "id": rc_id},
        )
        await session.commit()

        overdue_list = await get_overdue_reviews(session)
        assert len(overdue_list) == 1

        total = await count_records(session)
        assert total == 1

    async def test_json_serialization_roundtrip(self, session: AsyncSession):
        """Officers JSON serializes and deserializes correctly."""
        officers = sample_officers()
        raw = officers_to_json(officers)
        restored = json_to_officers(raw)
        assert len(restored) == 4
        assert restored[0].name == "Alice"
        assert restored[0].role == GovernanceOfficerRole.GOVERNANCE

    async def test_orm_model_relationship(self, session: AsyncSession):
        """GovernanceRecordModel loads review_cycle relationship."""
        from datetime import datetime, timezone

        rc = ReviewCycleModel(
            tenant_id="t1",
            interval_days=90,
            last_review_date=None,
            next_review_date=datetime.now(timezone.utc),
            status="active",
        )
        session.add(rc)
        await session.flush()

        gr = GovernanceRecordModel(
            tenant_id="t1",
            officers='[{"role": "governance", "name": "A", "email": "a@b.com"}]',
            review_cycle_id=rc.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status="active",
        )
        session.add(gr)
        await session.flush()
        await session.refresh(gr, ["review_cycle"])

        assert gr.review_cycle is not None
        assert gr.review_cycle.interval_days == 90
