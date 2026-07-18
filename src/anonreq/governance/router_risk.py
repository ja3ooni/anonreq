"""Risk assessment endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import _emit_sync, get_db
from anonreq.governance.risk import (
    check_config_triggers_reassessment,
    create_risk_assessment,
    flag_reassessment,
    get_risk_assessment,
    update_risk_assessment,
)
from anonreq.models.governance import RiskAssessment

router = APIRouter()


@router.post("/records/{tenant_id}/risk")
async def create_record_risk_assessment(
    tenant_id: str,
    payload: RiskAssessment,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/records/{tenant_id}/risk — create risk assessment."""
    try:
        assessment = await create_risk_assessment(
            db,
            tenant_id,
            payload.governance_record_id,
            payload.dimensions,
            payload.extensions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_created",
        metadata_json=f'{{"governance_record_id": {payload.governance_record_id}}}',
    )
    return assessment.model_dump()


@router.get("/records/{tenant_id}/risk")
async def get_record_risk_assessment(
    tenant_id: str,
    _request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/records/{tenant_id}/risk — get risk assessment."""
    assessment = await get_risk_assessment(db, tenant_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return assessment.model_dump()


@router.put("/records/{tenant_id}/risk")
async def update_record_risk_assessment(
    tenant_id: str,
    payload: RiskAssessment,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """PUT /v1/governance/records/{tenant_id}/risk — update risk assessment."""
    try:
        assessment = await update_risk_assessment(
            db, tenant_id, payload.dimensions, payload.extensions
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_updated",
        metadata_json='{"action": "update_risk"}',
    )
    return assessment.model_dump()


@router.post("/records/{tenant_id}/risk/reassess")
async def flag_risk_reassessment(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/records/{tenant_id}/risk/reassess — flag reassessment."""
    try:
        body = await request.json()
        reason = body.get("reason", "Manual reassessment request")
    except Exception:
        reason = "Manual reassessment request"

    try:
        assessment = await flag_reassessment(db, tenant_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_reassess",
        metadata_json=f'{{"reason": "{reason}"}}',
    )
    return assessment.model_dump()


@router.post("/config/trigger-reassessment")
async def trigger_config_reassessment(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/config/trigger-reassessment — check config triggers."""
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "default")
        changed_fields = body.get("changed_fields", [])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid request body") from exc

    flagged = await check_config_triggers_reassessment(db, tenant_id, changed_fields)

    _emit_sync(
        request,
        tenant_id,
        "config_reassessment_check",
        metadata_json=f'{{"flagged": {str(flagged).lower()}}}',
    )

    return {"reassessment_flagged": flagged}
