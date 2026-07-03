"""FastAPI router for governance records and risk assessment endpoints.

Provides CRUD endpoints for governance records, review cycle management,
risk assessment operations, and a governance status dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.governance.approval import ApprovalManager
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
)
from anonreq.governance.risk import (
    check_config_triggers_reassessment,
    create_risk_assessment,
    flag_reassessment,
    get_risk_assessment,
    update_risk_assessment,
)
from anonreq.models.audit import AuditEvent
from anonreq.models.governance import (
    GovernanceOfficer,
    GovernanceOfficerUpdate,
    GovernanceRecord,
    RiskAssessment,
    RiskDimensionScore,
)

governance_router = APIRouter(prefix="/v1/governance", tags=["governance"])
approval_router = APIRouter(prefix="/v1/oversight/approvals", tags=["approvals"])


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    engine: AsyncEngine = request.app.state.audit_engine
    async with async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )() as session:
        yield session


def _emit_sync(
    request: Request,
    tenant_id: str,
    event_type: str,
    operator_id: str | None = None,
    metadata_json: str | None = None,
) -> None:
    """Fire-and-forget audit event emission.

    Runs in the background to avoid blocking the response.
    """
    import asyncio

    chain = getattr(request.app.state, "audit_chain", None)
    if chain is None:
        return

    async def _emit():
        event = AuditEvent(
            event_id=f"gov_{uuid.uuid4().hex[:24]}",
            prev_hash=None,
            hash="",
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            request_id=getattr(request.state, "request_id", None),
            policy_id=None,
            decision=None,
            provider=None,
            latency_ms=None,
            event_type=event_type,
            operator_id=operator_id,
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json=metadata_json,
        )
        try:
            await chain.store_event(event)
        except Exception:
            pass

    asyncio.ensure_future(_emit())


@governance_router.get("/status")
async def governance_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/status — return governance record status.

    Returns total records, overdue reviews, upcoming reviews and
    a per-tenant breakdown of overdue items.
    """
    total = await count_records(db)
    overdue_list = await get_overdue_reviews(db)
    upcoming_list = await get_upcoming_reviews(db, days=30)

    now = datetime.now(timezone.utc)
    overdue_by_tenant = []
    for rec in overdue_list:
        if rec.review_cycle.next_review_date:
            days_overdue = (now - rec.review_cycle.next_review_date).days
            overdue_by_tenant.append(
                {"tenant_id": rec.tenant_id, "days_overdue": max(0, days_overdue)}
            )

    return {
        "total_records": total,
        "overdue_reviews": len(overdue_list),
        "upcoming_reviews_30d": len(upcoming_list),
        "overdue_by_tenant": overdue_by_tenant,
    }


@governance_router.get("/records")
async def list_records(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/records — paginated list of governance records."""
    records = await list_governance_records(db, skip=skip, limit=limit)
    return {"object": "list", "data": [r.model_dump() for r in records]}


@governance_router.get("/records/{tenant_id}")
async def get_record(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/records/{tenant_id} — get a specific record."""
    record = await get_governance_record(db, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Governance record not found")
    return record.model_dump()


@governance_router.put("/records/{tenant_id}")
async def update_record(
    tenant_id: str,
    payload: GovernanceOfficerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PUT /v1/governance/records/{tenant_id} — update officers."""
    try:
        record = await update_governance_record(db, tenant_id, payload.officers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _emit_sync(
        request,
        tenant_id,
        "governance_record_updated",
        metadata_json='{"action": "update_officers"}',
    )
    return record.model_dump()


@governance_router.post("/records/{tenant_id}/reviews")
async def complete_record_review(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/records/{tenant_id}/reviews — complete a review."""
    try:
        cycle = await complete_review(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _emit_sync(
        request,
        tenant_id,
        "governance_review_completed",
        metadata_json='{"action": "complete_review"}',
    )
    return cycle.model_dump()


@governance_router.post("/records/{tenant_id}/risk")
async def create_record_risk_assessment(
    tenant_id: str,
    payload: RiskAssessment,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
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
        raise HTTPException(status_code=422, detail=str(exc))

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_created",
        metadata_json=f'{{"governance_record_id": {payload.governance_record_id}}}',
    )
    return assessment.model_dump()


@governance_router.get("/records/{tenant_id}/risk")
async def get_record_risk_assessment(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/records/{tenant_id}/risk — get risk assessment."""
    assessment = await get_risk_assessment(db, tenant_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return assessment.model_dump()


@governance_router.put("/records/{tenant_id}/risk")
async def update_record_risk_assessment(
    tenant_id: str,
    payload: RiskAssessment,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PUT /v1/governance/records/{tenant_id}/risk — update risk assessment."""
    try:
        assessment = await update_risk_assessment(
            db, tenant_id, payload.dimensions, payload.extensions
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_updated",
        metadata_json='{"action": "update_risk"}',
    )
    return assessment.model_dump()


@governance_router.post("/records/{tenant_id}/risk/reassess")
async def flag_risk_reassessment(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/records/{tenant_id}/risk/reassess — flag reassessment."""
    try:
        body = await request.json()
        reason = body.get("reason", "Manual reassessment request")
    except Exception:
        reason = "Manual reassessment request"

    try:
        assessment = await flag_reassessment(db, tenant_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _emit_sync(
        request,
        tenant_id,
        "risk_assessment_reassess",
        metadata_json=f'{{"reason": "{reason}"}}',
    )
    return assessment.model_dump()


@governance_router.post("/config/trigger-reassessment")
async def trigger_config_reassessment(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/config/trigger-reassessment — check config triggers.

    Accepts JSON body with ``tenant_id`` and ``changed_fields``.
    Flags reassessment if entity-type-related fields changed.
    """
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "default")
        changed_fields = body.get("changed_fields", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    flagged = await check_config_triggers_reassessment(db, tenant_id, changed_fields)

    _emit_sync(
        request,
        tenant_id,
        "config_reassessment_check",
        metadata_json=f'{{"flagged": {str(flagged).lower()}}}',
    )

    return {"reassessment_flagged": flagged}


def _get_approval_manager(request: Request) -> ApprovalManager:
    mgr = getattr(request.app.state, "approval_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Approval manager not initialized")
    return mgr


@approval_router.post("")
async def create_approval(
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals — create a pending approval for a tool call.

    Creates a cryptographically random 256-bit token and stores the
    approval record in Valkey. The token is single-use and TTL-scoped.
    Returns HTTP 202-compatible response::

        {"approval_token": "...", "status": "pending"}
    """
    mgr = _get_approval_manager(request)
    try:
        body = await request.json()
        tool_call_dict = body.get("tool_call", {})
        context_dict = body.get("context", {})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    from anonreq.governance.tool_extractor import ToolCall
    from anonreq.models.processing_context import ProcessingContext

    tool_call = ToolCall(
        id=tool_call_dict.get("id", ""),
        name=tool_call_dict.get("name", ""),
        arguments=tool_call_dict.get("arguments", {}),
        format=tool_call_dict.get("format", "openai"),
        domain=tool_call_dict.get("domain", "model"),
        provider=tool_call_dict.get("provider"),
    )
    context = ProcessingContext(
        context_id=context_dict.get("context_id", ""),
        request_id=context_dict.get("request_id", ""),
        tenant_id=context_dict.get("tenant_id", "default"),
    )

    result = await mgr.create_approval(tool_call, context)
    return result


@approval_router.get("/{token}")
async def get_approval(
    token: str,
    request: Request,
) -> dict:
    """GET /v1/oversight/approvals/{token} — poll approval status.

    Returns::

        {"approval_token": "...", "status": "pending|approved|denied|expired|not_found"}
    """
    mgr = _get_approval_manager(request)
    return await mgr.get_approval_status(token)


@approval_router.post("/{token}/approve")
async def approve_tool_call(
    token: str,
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals/{token}/approve — approve a pending
    approval token. Body: ``{"decided_by": "...", "note": "..."}``.

    Returns the tool call context for execution::

        {"status": "approved", "decided_by": "...", "tool_call": {...}}
    """
    mgr = _get_approval_manager(request)
    try:
        body = await request.json()
        decided_by = body.get("decided_by", "unknown")
        note = body.get("note", "")
    except Exception:
        decided_by = "unknown"
        note = ""
    return await mgr.approve_approval(token, decided_by, note)


@approval_router.post("/{token}/deny")
async def deny_tool_call(
    token: str,
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals/{token}/deny — deny a pending
    approval token. Body: ``{"decided_by": "...", "note": "..."}``.
    """
    mgr = _get_approval_manager(request)
    try:
        body = await request.json()
        decided_by = body.get("decided_by", "unknown")
        note = body.get("note", "")
    except Exception:
        decided_by = "unknown"
        note = ""
    return await mgr.deny_approval(token, decided_by, note)


@approval_router.post("/cleanup")
async def cleanup_expired_approvals(
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals/cleanup — scan and delete expired
    approval tokens.
    """
    mgr = _get_approval_manager(request)
    deleted = await mgr.cleanup_expired()
    return {"deleted": deleted}
