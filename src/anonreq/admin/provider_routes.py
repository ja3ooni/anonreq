"""Admin provider inventory endpoints.

Provides:
- GET /v1/admin/providers — list providers (filterable by status, concentration_risk)
- GET /v1/admin/providers/{id} — get provider details
- POST /v1/admin/providers/{id}/suspend — suspend provider
- POST /v1/admin/providers/{id}/unsuspend — unsuspend provider
- POST /v1/admin/providers/{id}/concentration-risk — flag concentration risk

All endpoints require ADMINISTRATOR role per T-15-02-03/04 mitigation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from anonreq.middleware.rbac import Role, require_role

router = APIRouter(dependencies=[Depends(require_role(Role.ADMINISTRATOR))])


def _get_provider_inventory(request: Request):
    """Get ProviderInventory from app state."""
    inventory = getattr(request.app.state, "provider_inventory", None)
    if inventory is None:
        raise HTTPException(
            status_code=503,
            detail="Provider inventory not initialized",
        )
    return inventory


@router.get("/providers")
async def list_providers(
    request: Request,
    status: str | None = None,
    concentration_risk: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    """GET /v1/admin/providers — list provider records.

    Returns:
        Paginated list of provider records.
    """
    inventory = _get_provider_inventory(request)
    records = await inventory.list_providers(
        status=status,
        concentration_risk=concentration_risk,
        skip=skip,
        limit=limit,
    )
    return {"object": "list", "data": [r.model_dump() for r in records]}


@router.get("/providers/{provider_id}")
async def get_provider(
    request: Request,
    provider_id: str,
) -> dict:
    """GET /v1/admin/providers/{provider_id} — get provider details.

    Returns:
        Provider record details.

    Raises:
        HTTPException 404: If provider not found.
    """
    inventory = _get_provider_inventory(request)
    record = await inventory.get_provider_record(provider_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return record.model_dump()


@router.post("/providers/{provider_id}/suspend")
async def suspend_provider(
    request: Request,
    provider_id: str,
) -> dict:
    """POST /v1/admin/providers/{provider_id}/suspend — suspend a provider.

    Body: ``{"reason": "string", "suspended_by": "string"}``

    Returns:
        Updated provider record.

    Raises:
        HTTPException 404: If provider not found.
    """
    inventory = _get_provider_inventory(request)
    body = await request.json()
    reason = body.get("reason", "No reason provided")
    suspended_by = body.get("suspended_by", "unknown")

    try:
        record = await inventory.suspend_provider(
            provider_id=provider_id,
            reason=reason,
            suspended_by=suspended_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return record.model_dump()


@router.post("/providers/{provider_id}/unsuspend")
async def unsuspend_provider(
    request: Request,
    provider_id: str,
) -> dict:
    """POST /v1/admin/providers/{provider_id}/unsuspend — unsuspend a provider.

    Body: ``{"unsuspended_by": "string"}``

    Returns:
        Updated provider record.

    Raises:
        HTTPException 404: If provider not found.
    """
    inventory = _get_provider_inventory(request)
    body = await request.json()
    unsuspended_by = body.get("unsuspended_by", "unknown")

    try:
        record = await inventory.unsuspend_provider(
            provider_id=provider_id,
            unsuspended_by=unsuspended_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return record.model_dump()


@router.post("/providers/{provider_id}/concentration-risk")
async def flag_concentration_risk(
    request: Request,
    provider_id: str,
) -> dict:
    """POST /v1/admin/providers/{provider_id}/concentration-risk —
    flag concentration risk.

    Body: ``{"justification": "string"}``

    Returns:
        Updated provider record.

    Raises:
        HTTPException 404: If provider not found.
    """
    inventory = _get_provider_inventory(request)
    body = await request.json()
    justification = body.get("justification", "No justification provided")

    try:
        record = await inventory.flag_concentration_risk(
            provider_id=provider_id,
            justification=justification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return record.model_dump()
