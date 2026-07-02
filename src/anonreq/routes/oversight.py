"""FastAPI routes for human oversight: approval queue and kill-switch.

Endpoints:
- ``GET /v1/oversight/approvals`` — list pending approvals
- ``GET /v1/oversight/approvals/{approval_id}`` — get single approval
- ``POST /v1/oversight/approvals/{approval_id}/approve`` — approve
- ``POST /v1/oversight/approvals/{approval_id}/reject`` — reject
- ``GET /v1/oversight/kill-switch`` — get kill-switch status
- ``POST /v1/oversight/kill-switch`` — activate/deactivate
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from anonreq.services.oversight import (
    ApprovalRequestCreate,
    OversightService,
)

router = APIRouter(prefix="/v1/oversight", tags=["oversight"])


def _get_service(request: Request) -> OversightService:
    svc = getattr(request.app.state, "oversight_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Oversight service not initialized")
    return svc


@router.get("/approvals")
async def list_approvals(
    request: Request,
    tenant_id: str | None = None,
) -> dict:
    """GET /v1/oversight/approvals — list pending approvals (optionally filtered by tenant)."""
    svc = _get_service(request)
    approvals = await svc.list_pending_approvals(tenant_id=tenant_id)
    return {
        "object": "list",
        "data": [a.model_dump() for a in approvals],
    }


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    request: Request,
) -> dict:
    """GET /v1/oversight/approvals/{approval_id} — get single approval."""
    svc = _get_service(request)
    req = await svc.get_approval_request(approval_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req.model_dump()


@router.post("/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals/{approval_id}/approve — approve a request."""
    svc = _get_service(request)
    try:
        body = await request.json()
        operator_id = body.get("operator_id", "unknown")
    except Exception:
        operator_id = "unknown"
    try:
        req = await svc.approve_request(approval_id, operator_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc))
    return req.model_dump()


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    request: Request,
) -> dict:
    """POST /v1/oversight/approvals/{approval_id}/reject — reject a request."""
    svc = _get_service(request)
    try:
        body = await request.json()
        operator_id = body.get("operator_id", "unknown")
    except Exception:
        operator_id = "unknown"
    try:
        req = await svc.reject_request(approval_id, operator_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc))
    return req.model_dump()


@router.get("/kill-switch")
async def get_kill_switch(request: Request) -> dict:
    """GET /v1/oversight/kill-switch — return current kill-switch status."""
    svc = _get_service(request)
    status = await svc.get_kill_switch_status()
    return status.model_dump()


@router.post("/kill-switch")
async def post_kill_switch(request: Request) -> dict:
    """POST /v1/oversight/kill-switch — activate or deactivate.

    Body (activate): ``{"action": "activate", "operator_id": "...", "reason": "..."}``
    Body (deactivate): ``{"action": "deactivate", "operator_id": "..."}``
    """
    svc = _get_service(request)
    try:
        body = await request.json()
        action = body.get("action", "activate")
        operator_id = body.get("operator_id", "unknown")
        reason = body.get("reason", "No reason provided")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if action == "activate":
        await svc.activate_kill_switch(operator_id, reason)
        return {"status": "kill_switch_activated", "operator_id": operator_id, "reason": reason}
    elif action == "deactivate":
        await svc.deactivate_kill_switch(operator_id)
        return {"status": "kill_switch_deactivated", "operator_id": operator_id}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
