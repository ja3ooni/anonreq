"""Governance and audit trail routes.

Provides endpoints for audit chain status, verification, and
retrieval via the AuditChainService and ChainAnchorService.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request

from anonreq.middleware.rbac import Role, require_role

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


@router.get("/status", dependencies=[Depends(require_role(Role.ADMINISTRATOR))])
async def get_governance_status(
    request: Request,
    tenant_id: str = "default",
) -> dict:
    """Return SLO compliance for all configured SLOs."""
    slo_engine = getattr(request.app.state, "slo_engine", None)
    if slo_engine is None:
        raise HTTPException(status_code=503, detail="SLO engine not initialized")
    
    compliance = await slo_engine.get_all_compliance(tenant_id)
    
    # Format slos list or dict
    slos_data = {}
    for sname, comps in compliance.items():
        slos_data[sname] = [
            {
                "window_type": c.window_type,
                "window_key": c.window_key,
                "target": c.target,
                "current": c.current,
                "compliant": c.compliant,
                "last_breach": c.last_breach.isoformat() if c.last_breach else None,
            }
            for c in comps
        ]

    return {
        "tenant_id": tenant_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "slos": slos_data,
    }


@router.get("/breaches", dependencies=[Depends(require_role(Role.ADMINISTRATOR))])
async def list_governance_breaches(
    request: Request,
    tenant_id: str = "default",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return recent SLO breach events from the audit chain."""
    chain = getattr(request.app.state, "audit_chain", None)
    if chain is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")
    
    events = await chain.get_events(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        event_type="slo_breach_detected",
    )
    
    # Format response
    data = []
    for e in events:
        metadata = {}
        if e.metadata_json:
            try:
                metadata = json.loads(e.metadata_json)
            except Exception:
                pass
        data.append({
            "event_id": e.event_id,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "tenant_id": e.tenant_id,
            "details": metadata,
        })

    return {
        "object": "list",
        "data": data,
        "limit": limit,
        "offset": offset,
    }
