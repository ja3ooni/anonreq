"""Governance status and records CRUD endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import _emit_sync, get_db
from anonreq.governance.records import (
    get_governance_record,
    list_governance_records,
    update_governance_record,
)
from anonreq.governance.reviews import (
    complete_review,
    count_records,
    get_overdue_reviews,
    get_upcoming_reviews,
)
from anonreq.models.governance import GovernanceOfficerUpdate

router = APIRouter()


@router.get("/status")
async def governance_status(
    _request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/status — return governance record status."""
    from anonreq.governance.supplier import SupplierGovernance
    from anonreq.retention.legal_hold import LegalHoldManager

    total = await count_records(db)
    overdue_list = await get_overdue_reviews(db)
    upcoming_list = await get_upcoming_reviews(db, days=30)

    now = datetime.now(UTC)
    overdue_by_tenant = []
    for rec in overdue_list:
        if rec.review_cycle.next_review_date:
            days_overdue = (now - rec.review_cycle.next_review_date).days
            overdue_by_tenant.append(
                {"tenant_id": rec.tenant_id, "days_overdue": max(0, days_overdue)}
            )

    lh_mgr = LegalHoldManager(db)
    active_holds = await lh_mgr.list_active_holds()

    sup_gov = SupplierGovernance(db)
    supplier_overdue = await sup_gov.get_overdue_reviews()

    return {
        "total_records": total,
        "overdue_reviews": len(overdue_list),
        "upcoming_reviews_30d": len(upcoming_list),
        "overdue_by_tenant": overdue_by_tenant,
        "active_legal_holds": len(active_holds),
        "overdue_supplier_reviews": len(supplier_overdue),
    }


@router.get("/records")
async def list_records(
    _request: Request,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/records — paginated list of governance records."""
    records = await list_governance_records(db, skip=skip, limit=limit)
    return {"object": "list", "data": [r.model_dump() for r in records]}


@router.get("/records/{tenant_id}")
async def get_record(
    tenant_id: str,
    _request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/records/{tenant_id} — get a specific record."""
    record = await get_governance_record(db, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Governance record not found")
    return record.model_dump()


@router.put("/records/{tenant_id}")
async def update_record(
    tenant_id: str,
    payload: GovernanceOfficerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """PUT /v1/governance/records/{tenant_id} — update officers."""
    try:
        record = await update_governance_record(db, tenant_id, payload.officers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _emit_sync(
        request,
        tenant_id,
        "governance_record_updated",
        metadata_json='{"action": "update_officers"}',
    )
    return record.model_dump()


@router.post("/records/{tenant_id}/reviews")
async def complete_record_review(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/records/{tenant_id}/reviews — complete a review."""
    try:
        cycle = await complete_review(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _emit_sync(
        request,
        tenant_id,
        "governance_review_completed",
        metadata_json='{"action": "complete_review"}',
    )
    return cycle.model_dump()
