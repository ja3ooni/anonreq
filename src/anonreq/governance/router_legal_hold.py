"""Legal hold endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import get_db

router = APIRouter()


def _parse_optional_dt(value: str | None) -> datetime | None:
    """Parse ISO datetime string or return None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


@router.get("/legal-holds")
async def list_legal_holds(
    _request: Request,
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/legal-holds — list active legal holds."""
    from anonreq.retention.legal_hold import LegalHoldManager

    mgr = LegalHoldManager(db)
    holds = await mgr.list_active_holds(tenant_id=tenant_id)
    return {"object": "list", "data": [h.model_dump() for h in holds]}


@router.post("/legal-holds")
async def create_legal_hold(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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


@router.post("/legal-holds/{hold_id}/release")
async def release_legal_hold(
    hold_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/legal-holds/{hold_id}/release — release a hold."""
    from anonreq.retention.legal_hold import LegalHoldManager

    body = await request.json()
    mgr = LegalHoldManager(db)
    try:
        released = await mgr.release_hold(
            hold_id, released_by=body.get("released_by", "unknown")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return released.model_dump()
