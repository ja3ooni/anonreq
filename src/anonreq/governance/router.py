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

    Returns total records, overdue reviews, upcoming reviews,
    a per-tenant breakdown of overdue items, active legal hold count,
    and overdue supplier reviews.
    """
    from anonreq.retention.legal_hold import LegalHoldManager
    from anonreq.governance.supplier import SupplierGovernance

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

    # Legal Hold status
    lh_mgr = LegalHoldManager(db)
    active_holds = await lh_mgr.list_active_holds()

    # Supplier governance status
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


# ── Legal Hold endpoints ──────────────────────────────────────────────────────


@governance_router.get("/legal-holds")
async def list_legal_holds(
    request: Request,
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/legal-holds — list active legal holds."""
    from anonreq.retention.legal_hold import LegalHoldManager

    mgr = LegalHoldManager(db)
    holds = await mgr.list_active_holds(tenant_id=tenant_id)
    return {"object": "list", "data": [h.model_dump() for h in holds]}


@governance_router.post("/legal-holds")
async def create_legal_hold(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/legal-holds — create a legal hold."""
    from anonreq.retention.legal_hold import LegalHoldManager

    body = await request.json()
    mgr = LegalHoldManager(db)
    hold = await mgr.activate_hold(
        tenant_id=body["tenant_id"],
        reason=body.get("reason", ""),
        activated_by=body.get("activated_by", "unknown"),
        scope=body.get("scope", "tenant"),
        record_id=body.get("record_id"),
        expires_at=_parse_optional_dt(body.get("expires_at")),
    )
    return hold.model_dump()


@governance_router.post("/legal-holds/{hold_id}/release")
async def release_legal_hold(
    hold_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/legal-holds/{hold_id}/release — release a hold."""
    from anonreq.retention.legal_hold import LegalHoldManager

    body = await request.json()
    mgr = LegalHoldManager(db)
    try:
        released = await mgr.release_hold(
            hold_id, released_by=body.get("released_by", "unknown")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return released.model_dump()


# ── Supplier governance endpoints ────────────────────────────────────────────


@governance_router.get("/suppliers")
async def list_suppliers(
    request: Request,
    risk_status: str | None = None,
    contract_status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/suppliers — list suppliers with optional filters."""
    from anonreq.governance.supplier import SupplierGovernance

    gov = SupplierGovernance(db)
    suppliers = await gov.list_suppliers(
        risk_status=risk_status, contract_status=contract_status
    )
    return {"object": "list", "data": [s.model_dump() for s in suppliers]}


@governance_router.post("/suppliers")
async def create_supplier(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/suppliers — create a supplier record."""
    from anonreq.governance.supplier import SupplierGovernance

    body = await request.json()
    gov = SupplierGovernance(db)
    supplier = await gov.create_supplier(
        name=body["name"],
        provider_type=body.get("provider_type", "llm"),
        contract_status=body.get("contract_status", "active"),
        risk_status=body.get("risk_status", "low"),
    )
    return supplier.model_dump()


@governance_router.get("/suppliers/overdue-reviews")
async def get_supplier_overdue_reviews(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/suppliers/overdue-reviews — list overdue reviews."""
    from anonreq.governance.supplier import SupplierGovernance

    gov = SupplierGovernance(db)
    overdue = await gov.get_overdue_reviews()
    return {"object": "list", "data": [s.model_dump() for s in overdue]}


@governance_router.post("/suppliers/{supplier_id}/re-evaluate")
async def trigger_supplier_risk_re_evaluation(
    supplier_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/suppliers/{supplier_id}/re-evaluate — trigger re-eval."""
    from anonreq.governance.supplier import SupplierGovernance

    body = await request.json()
    gov = SupplierGovernance(db)
    try:
        result = await gov.trigger_risk_re_evaluation(
            supplier_id, trigger=body.get("trigger", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result.model_dump()


def _parse_optional_dt(value: str | None) -> datetime | None:
    """Parse ISO datetime string or return None."""
    if not value:
        return None
    try:
        from datetime import timezone

        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# ── DSAR endpoints ────────────────────────────────────────────────────────────


@governance_router.post("/dsar/requests")
async def submit_request(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/dsar/requests — submit a DSAR request."""
    from anonreq.dsar.workflow import DsarWorkflow

    body = await request.json()
    workflow = DsarWorkflow(db)
    subject_id = body.get("subject_id", body.get("tenant_id", "default"))
    dsar_request = await workflow.submit_request(
        subject_id=subject_id,
        request_type=body["request_type"],
        notes=body.get("notes"),
        tenant_id=body.get("tenant_id", "default"),
    )
    return dsar_request.model_dump()


@governance_router.get("/dsar/requests")
async def list_dsar_requests(
    request: Request,
    tenant_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/dsar/requests — list DSAR requests with filters."""
    from anonreq.dsar.workflow import DsarWorkflow

    workflow = DsarWorkflow(db)
    requests_list = await workflow.list_requests(
        tenant_id=tenant_id, status=status
    )
    return {"object": "list", "data": [r.model_dump() for r in requests_list]}


@governance_router.get("/dsar/requests/{request_id}")
async def get_dsar_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/dsar/requests/{request_id} — get request status."""
    from anonreq.dsar.workflow import DsarWorkflow

    workflow = DsarWorkflow(db)
    dsar_request = await workflow.get_request_status(request_id)
    if dsar_request is None:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    return dsar_request.model_dump()


@governance_router.post("/dsar/requests/{request_id}/fulfill")
async def fulfill_dsar_request(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/dsar/requests/{request_id}/fulfill — fulfill."""
    from anonreq.dsar.workflow import DsarWorkflow

    body = await request.json()
    workflow = DsarWorkflow(db)
    try:
        result = await workflow.fulfill_request(
            request_id=request_id,
            fulfilled_by=body.get("fulfilled_by", "unknown"),
            notes=body.get("notes"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result.model_dump()


@governance_router.post("/dsar/erasure/{subject_id}")
async def erase_subject_data(
    subject_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/dsar/erasure/{subject_id} — erase subject data."""
    from anonreq.dsar.erasure import DataErasureService

    service = DataErasureService(db)
    erased = await service.erase_subject_data(subject_id)
    return {"subject_id": subject_id, "erased": erased, "erased_at": datetime.now(timezone.utc).isoformat()}


@governance_router.get("/dsar/erasure/{subject_id}")
async def check_subject_erasure(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/dsar/erasure/{subject_id} — check erasure status."""
    from anonreq.dsar.erasure import DataErasureService

    service = DataErasureService(db)
    erased = await service.has_been_erased(subject_id)
    return {"subject_id": subject_id, "erased": erased}


@governance_router.post("/dsar/restriction/{subject_id}")
async def restrict_subject(
    subject_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/dsar/restriction/{subject_id} — restrict processing."""
    from anonreq.dsar.restriction import DataRestrictionService

    body = await request.json()
    service = DataRestrictionService(db)
    await service.restrict_subject(
        subject_id,
        reason=body.get("reason", ""),
        restricted_by=body.get("restricted_by", "unknown"),
    )
    return {"subject_id": subject_id, "restricted": True}


@governance_router.get("/dsar/restriction/{subject_id}")
async def check_subject_restriction(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/dsar/restriction/{subject_id} — check restriction."""
    from anonreq.dsar.restriction import DataRestrictionService

    service = DataRestrictionService(db)
    restricted = await service.is_subject_restricted(subject_id)
    return {"subject_id": subject_id, "restricted": restricted}


@governance_router.delete("/dsar/restriction/{subject_id}")
async def remove_subject_restriction(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """DELETE /v1/governance/dsar/restriction/{subject_id} — remove restriction."""
    from anonreq.dsar.restriction import DataRestrictionService

    service = DataRestrictionService(db)
    removed = await service.remove_restriction(subject_id)
    return {"subject_id": subject_id, "removed": removed}


@governance_router.get("/dsar/restrictions")
async def list_restricted_subjects(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/dsar/restrictions — list restricted subjects."""
    from anonreq.dsar.restriction import DataRestrictionService

    service = DataRestrictionService(db)
    subjects = await service.list_restricted_subjects()
    return {"object": "list", "data": subjects}


# ── Breach notification endpoints ─────────────────────────────────────────────


@governance_router.post("/breach/notify")
async def send_breach_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/breach/notify — send breach notifications."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    body = await request.json()
    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    result = await notifier.send_breach_notifications(
        breach_id=body["breach_id"],
        framework=body.get("framework", "gdpr"),
        description=body.get("description", ""),
        affected_tenants=body.get("affected_tenants", []),
    )
    return result


@governance_router.get("/breach/queue")
async def get_breach_notification_queue(
    request: Request,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /v1/governance/breach/queue — get notification queue."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    queue = await notifier.get_notification_queue(status=status)
    return {"object": "list", "data": queue}


@governance_router.post("/breach/retry")
async def retry_failed_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /v1/governance/breach/retry — retry failed notifications."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    count = await notifier.retry_failed_notifications()
    return {"retried": count}


@governance_router.get("/breach/templates")
async def list_breach_templates(
    request: Request,
) -> dict:
    """GET /v1/governance/breach/templates — list available templates."""
    from anonreq.breach.templates import BreachTemplateManager

    mgr = BreachTemplateManager()
    templates = mgr.list_available_templates()
    return {"object": "list", "data": templates}


@governance_router.post("/breach/templates")
async def set_breach_custom_template(
    request: Request,
) -> dict:
    """POST /v1/governance/breach/templates — set custom template."""
    from anonreq.breach.templates import BreachTemplateManager
    from anonreq.models.breach import BreachTemplate

    body = await request.json()
    mgr = BreachTemplateManager()
    custom = BreachTemplate(
        id=body.get("id", f"custom-{body['framework']}-{body['region']}"),
        framework=body["framework"],
        region=body["region"],
        subject_template=body["subject_template"],
        body_template=body["body_template"],
    )
    import asyncio

    await mgr.set_custom_template(body["framework"], body["region"], custom)
    return {"status": "ok", "template_id": custom.id}


# ── Approval manager endpoint ────────────────────────────────────────────────


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
