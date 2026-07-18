"""Review cycle scheduling and overdue detection.

Provides async functions for scheduling reviews, detecting overdue
reviews, and completing review cycles.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from anonreq.models.governance import (
    GovernanceRecord,
    GovernanceRecordModel,
    ReviewCycle,
    ReviewCycleModel,
)


async def schedule_review(
    db: AsyncSession,
    tenant_id: str,
    interval_days: int = 90,
) -> ReviewCycle:
    """Create or update a review cycle for a tenant.

    If a cycle already exists, updates its interval and next_review_date.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        interval_days: Review interval in days (default 90).

    Returns:
        The ReviewCycle.
    """
    stmt = select(ReviewCycleModel).where(
        ReviewCycleModel.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    existing = result.scalars().one_or_none()

    now = datetime.now(UTC)
    next_review = (now + timedelta(days=interval_days)).replace(microsecond=0)

    if existing:
        existing.interval_days = cast(Column[int], interval_days)
        existing.next_review_date = cast(Column[datetime], next_review)
        existing.status = cast(Column[str], "active")
        await db.flush()
        model = existing
    else:
        model = ReviewCycleModel(
            tenant_id=tenant_id,
            interval_days=interval_days,
            last_review_date=None,
            next_review_date=next_review,
            status="active",
        )
        db.add(model)
        await db.flush()

    return ReviewCycle(
        id=model.id,
        tenant_id=model.tenant_id,
        interval_days=model.interval_days,
        last_review_date=_ensure_tz(cast(datetime | None, model.last_review_date)),
        next_review_date=_ensure_tz(cast(datetime | None, model.next_review_date)),
        status=model.status,
    )


async def get_overdue_reviews(
    db: AsyncSession,
) -> list[GovernanceRecord]:
    """Find governance records where next_review_date is in the past.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of GovernanceRecords with overdue reviews.
    """
    now = datetime.now(UTC)
    stmt = (
        select(GovernanceRecordModel)
        .options(joinedload(GovernanceRecordModel.review_cycle))
        .join(ReviewCycleModel)
        .where(ReviewCycleModel.next_review_date < now)
        .where(GovernanceRecordModel.status == "active")
        .where(ReviewCycleModel.status == "active")
    )
    result = await db.execute(stmt)
    models = result.scalars().unique().all()
    return [_model_to_record(m) for m in models]


async def get_upcoming_reviews(
    db: AsyncSession,
    days: int = 30,
) -> list[GovernanceRecord]:
    """Find governance records with reviews due within the given days.

    Args:
        db: Async SQLAlchemy session.
        days: Look-ahead window in days (default 30).

    Returns:
        List of GovernanceRecords with upcoming reviews.
    """
    now = datetime.now(UTC)
    horizon = (now + timedelta(days=days)).replace(microsecond=0)
    stmt = (
        select(GovernanceRecordModel)
        .options(joinedload(GovernanceRecordModel.review_cycle))
        .join(ReviewCycleModel)
        .where(ReviewCycleModel.next_review_date >= now)
        .where(ReviewCycleModel.next_review_date <= horizon)
        .where(ReviewCycleModel.status == "active")
    )
    result = await db.execute(stmt)
    models = result.scalars().unique().all()
    return [_model_to_record(m) for m in models]


async def complete_review(
    db: AsyncSession,
    tenant_id: str,
) -> ReviewCycle:
    """Complete the current review cycle and schedule the next one.

    Sets last_review_date to the current time and advances
    next_review_date by interval_days.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.

    Returns:
        Updated ReviewCycle.

    Raises:
        ValueError: If no review cycle exists for tenant_id.
    """
    stmt = select(ReviewCycleModel).where(
        ReviewCycleModel.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    model = result.scalars().one_or_none()
    if model is None:
        raise ValueError(f"No review cycle for tenant: {tenant_id}")

    now = datetime.now(UTC)
    model.last_review_date = cast(Column[datetime], now)
    next_review = (now + timedelta(days=cast(int, model.interval_days))).replace(
        microsecond=0
    )
    model.next_review_date = cast(Column[datetime], next_review)
    await db.flush()

    return ReviewCycle(
        id=model.id,
        tenant_id=model.tenant_id,
        interval_days=model.interval_days,
        last_review_date=_ensure_tz(cast(datetime | None, model.last_review_date)),
        next_review_date=_ensure_tz(cast(datetime | None, model.next_review_date)),
        status=model.status,
    )


async def count_records(db: AsyncSession) -> int:
    """Count total active governance records.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        Total count of active records.
    """
    from sqlalchemy import func

    stmt = select(func.count()).select_from(GovernanceRecordModel).where(
        GovernanceRecordModel.status == "active"
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


def _model_to_record(model: GovernanceRecordModel) -> GovernanceRecord:
    """Convert ORM model to Pydantic GovernanceRecord."""
    import json

    officers_data = json.loads(cast(str, model.officers))
    from anonreq.models.governance import (
        GovernanceOfficer,
        json_to_change_history,
    )

    officers = [GovernanceOfficer(**o) for o in officers_data]

    rc = model.review_cycle
    review_cycle = ReviewCycle(
        id=rc.id,
        tenant_id=rc.tenant_id,
        interval_days=rc.interval_days,
        last_review_date=_ensure_tz(cast(datetime | None, rc.last_review_date)),
        next_review_date=_ensure_tz(cast(datetime | None, rc.next_review_date)),
        status=rc.status,
    )

    change_history = json_to_change_history(
        getattr(model, "change_history", None)
    )

    return GovernanceRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        officers=officers,
        review_cycle=review_cycle,
        created_at=_ensure_tz(cast(datetime | None, model.created_at)),
        updated_at=_ensure_tz(cast(datetime | None, model.updated_at)),
        status=model.status,
        version=getattr(model, "version", 1),
        change_history=change_history,
    )


def _ensure_tz(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
