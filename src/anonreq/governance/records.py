"""Governance record CRUD operations over PostgreSQL.

Provides async functions for managing governance records,
including creation, retrieval, update, and paginated listing.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from anonreq.models.governance import (
    ChangeEntry,
    GovernanceOfficer,
    GovernanceRecord,
    GovernanceRecordModel,
    ReviewCycle,
    ReviewCycleModel,
    change_history_to_json,
    json_to_change_history,
    officers_to_json,
)


async def create_governance_record(
    db: AsyncSession,
    tenant_id: str,
    officers: list[GovernanceOfficer],
    interval_days: int = 90,
) -> GovernanceRecord:
    """Create a governance record with a new review cycle.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        officers: List of GovernanceOfficer assignments.
        interval_days: Review cycle interval (default 90).

    Returns:
        The created GovernanceRecord with nested ReviewCycle.
    """
    now = datetime.now(timezone.utc)
    next_review = (now + timedelta(days=interval_days)).replace(microsecond=0)

    review_cycle = ReviewCycleModel(
        tenant_id=tenant_id,
        interval_days=interval_days,
        last_review_date=None,
        next_review_date=next_review,
        status="active",
    )
    db.add(review_cycle)
    await db.flush()

    record = GovernanceRecordModel(
        tenant_id=tenant_id,
        officers=officers_to_json(officers),
        review_cycle_id=review_cycle.id,
        created_at=now,
        updated_at=now,
        status="active",
    )
    db.add(record)
    await db.flush()
    await db.refresh(record, ["review_cycle"])

    return _model_to_record(record)


async def get_governance_record(
    db: AsyncSession,
    tenant_id: str,
) -> GovernanceRecord | None:
    """Fetch a governance record by tenant_id.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.

    Returns:
        GovernanceRecord or None if not found.
    """
    stmt = (
        select(GovernanceRecordModel)
        .options(joinedload(GovernanceRecordModel.review_cycle))
        .where(GovernanceRecordModel.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    model = result.scalars().unique().one_or_none()
    if model is None:
        return None
    return _model_to_record(model)


async def update_governance_record(
    db: AsyncSession,
    tenant_id: str,
    officers: list[GovernanceOfficer],
) -> GovernanceRecord:
    """Update officers on an existing governance record.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        officers: New list of GovernanceOfficer assignments.

    Returns:
        Updated GovernanceRecord.

    Raises:
        ValueError: If no record exists for tenant_id.
    """
    stmt = (
        select(GovernanceRecordModel)
        .options(joinedload(GovernanceRecordModel.review_cycle))
        .where(GovernanceRecordModel.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    model = result.scalars().unique().one_or_none()
    if model is None:
        raise ValueError(f"No governance record for tenant: {tenant_id}")

    # Record the change in change_history for audit trail
    now = datetime.now(timezone.utc)
    existing_history = json_to_change_history(
        getattr(model, "change_history", None)
    )
    next_version = max((e.version for e in existing_history), default=0) + 1

    old_officers = json.loads(model.officers)
    changes_desc = {}
    old_names = {o["name"] for o in old_officers}
    new_names = {o.name for o in officers}
    if old_names != new_names:
        changes_desc["officers"] = (
            f"updated from {len(old_officers)} to {len(officers)} officers"
        )

    new_entry = ChangeEntry(
        version=next_version,
        changed_at=now,
        changed_by="system",
        description=f"Governance record updated to version {next_version}",
        changes=changes_desc,
    )
    updated_history = existing_history + [new_entry]

    model.officers = officers_to_json(officers)
    model.change_history = change_history_to_json(updated_history)
    model.version = next_version
    model.updated_at = now
    await db.flush()
    await db.refresh(model, ["review_cycle"])
    return _model_to_record(model)


async def list_governance_records(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
) -> list[GovernanceRecord]:
    """List governance records with pagination.

    Args:
        db: Async SQLAlchemy session.
        skip: Number of records to skip.
        limit: Maximum records to return.

    Returns:
        List of GovernanceRecord objects.
    """
    stmt = (
        select(GovernanceRecordModel)
        .options(joinedload(GovernanceRecordModel.review_cycle))
        .offset(skip)
        .limit(limit)
        .order_by(GovernanceRecordModel.created_at.desc())
    )
    result = await db.execute(stmt)
    models = result.scalars().unique().all()
    return [_model_to_record(m) for m in models]


def _model_to_record(model: GovernanceRecordModel) -> GovernanceRecord:
    """Convert ORM model to Pydantic GovernanceRecord."""
    officers_data = json.loads(model.officers)
    officers = [GovernanceOfficer(**o) for o in officers_data]

    rc = model.review_cycle
    review_cycle = ReviewCycle(
        id=rc.id,
        tenant_id=rc.tenant_id,
        interval_days=rc.interval_days,
        last_review_date=_ensure_tz(rc.last_review_date),
        next_review_date=_ensure_tz(rc.next_review_date),
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
        created_at=_ensure_tz(model.created_at),
        updated_at=_ensure_tz(model.updated_at),
        status=model.status,
        version=getattr(model, "version", 1),
        change_history=change_history,
    )


def _ensure_tz(dt: Any) -> Any:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
