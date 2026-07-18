"""Approval manager endpoints."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request

from anonreq.governance.approval import ApprovalManager
from anonreq.state import get_app_state

approval_router = APIRouter(prefix="/v1/oversight/approvals", tags=["approvals"])


def _get_approval_manager(request: Request) -> ApprovalManager:
    mgr: Any = get_app_state(request.app).approval_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Approval manager not initialized")
    return cast(ApprovalManager, mgr)


@approval_router.post("")
async def create_approval(
    request: Request,
) -> dict[str, Any]:
    """POST /v1/oversight/approvals — create a pending approval for a tool call."""
    mgr = _get_approval_manager(request)
    try:
        body = await request.json()
        tool_call_dict = body.get("tool_call", {})
        context_dict = body.get("context", {})
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid request body") from exc

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
) -> dict[str, Any]:
    """GET /v1/oversight/approvals/{token} — poll approval status."""
    mgr = _get_approval_manager(request)
    return await mgr.get_approval_status(token)


@approval_router.post("/{token}/approve")
async def approve_tool_call(
    token: str,
    request: Request,
) -> dict[str, Any]:
    """POST /v1/oversight/approvals/{token}/approve — approve a pending approval."""
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
) -> dict[str, Any]:
    """POST /v1/oversight/approvals/{token}/deny — deny a pending approval."""
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
) -> dict[str, Any]:
    """POST /v1/oversight/approvals/cleanup — scan and delete expired tokens."""
    mgr = _get_approval_manager(request)
    deleted = await mgr.cleanup_expired()
    return {"deleted": deleted}
