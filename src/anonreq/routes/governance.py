"""Governance and audit trail routes.

Provides endpoints for audit chain status, verification, and
retrieval via the AuditChainService and ChainAnchorService.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/v1/governance", tags=["governance"])


@router.get("/audit/status")
async def governance_audit_status(request: Request) -> dict:
    """GET /v1/governance/audit/status — return audit chain and anchor status.

    Requires ``audit_chain`` and ``chain_anchor`` services to be
    initialized on app state. Returns metadata about the current
    state of the audit trail.
    """
    chain = getattr(request.app.state, "audit_chain", None)
    anchor = getattr(request.app.state, "chain_anchor", None)
    if chain is None or anchor is None:
        raise HTTPException(status_code=503, detail="Audit services not initialized")

    anchor_status = await anchor.get_anchor_status()
    return {
        "service": "anonreq-governance",
        "anchor": anchor_status,
    }


@router.get("/audit/events")
async def list_audit_events(
    request: Request,
    tenant_id: str = "default",
    limit: int = 100,
    offset: int = 0,
    event_type: str | None = None,
) -> dict:
    """GET /v1/governance/audit/events — paginated audit event list.

    Returns events with their hash chain metadata.
    """
    chain = getattr(request.app.state, "audit_chain", None)
    if chain is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    events = await chain.get_events(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
    )
    return {
        "object": "list",
        "data": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "prev_hash": e.prev_hash,
                "hash": e.hash,
                "timestamp": e.timestamp.isoformat(),
                "tenant_id": e.tenant_id,
            }
            for e in events
        ],
    }


@router.get("/audit/verify")
async def verify_audit_chain(request: Request, tenant_id: str = "default") -> dict:
    """GET /v1/governance/audit/verify — verify hash chain integrity.

    Walks the entire chain and reports whether any tampering is detected.
    """
    chain = getattr(request.app.state, "audit_chain", None)
    if chain is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    result = await chain.verify_chain(tenant_id=tenant_id)
    return {
        "is_intact": result.is_intact,
        "checked_count": result.checked_count,
        "broken_at": result.broken_at,
    }
