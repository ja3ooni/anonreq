"""DSAR (Data Subject Access Request) endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import get_db
from anonreq.state import get_app_state

router = APIRouter()


@router.post("/dsar/requests")
async def submit_request(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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


@router.get("/dsar/requests")
async def list_dsar_requests(
    _request: Request,
    tenant_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/dsar/requests — list DSAR requests with filters."""
    from anonreq.dsar.workflow import DsarWorkflow

    workflow = DsarWorkflow(db)
    requests_list = await workflow.list_requests(
        tenant_id=tenant_id, status=status
    )
    return {"object": "list", "data": [r.model_dump() for r in requests_list]}


@router.get("/dsar/requests/{request_id}")
async def get_dsar_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/dsar/requests/{request_id} — get request status."""
    from anonreq.dsar.workflow import DsarWorkflow

    workflow = DsarWorkflow(db)
    dsar_request = await workflow.get_request_status(request_id)
    if dsar_request is None:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    return dsar_request.model_dump()


@router.post("/dsar/requests/{request_id}/fulfill")
async def fulfill_dsar_request(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/dsar/requests/{request_id}/fulfill — fulfill."""
    from anonreq.dsar.workflow import DsarWorkflow

    body = await request.json()
    workflow = DsarWorkflow(db)
    try:
        result = await workflow.fulfill_request(
            request_id=request_id,
            fulfilled_by=body.get("fulfilled_by", "unknown"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/dsar/erasure/{subject_id}")
async def erase_subject_data(
    subject_id: str,
    _request: Request,
) -> dict[str, Any]:
    """POST /v1/governance/dsar/erasure/{subject_id} — erase subject data."""
    from anonreq.dsar.erasure import DataErasureService

    cache = get_app_state(_request.app).cache_manager
    assert cache is not None
    service = DataErasureService(cache)
    erased = await service.erase_subject_data(subject_id)
    return {"subject_id": subject_id, "erased": erased, "erased_at": datetime.now(UTC).isoformat()}


@router.get("/dsar/erasure/{subject_id}")
async def check_subject_erasure(
    subject_id: str,
    _request: Request,
) -> dict[str, Any]:
    """GET /v1/governance/dsar/erasure/{subject_id} — check erasure status."""
    from anonreq.dsar.erasure import DataErasureService

    cache = get_app_state(_request.app).cache_manager
    assert cache is not None
    service = DataErasureService(cache)
    erased = await service.has_been_erased(subject_id)
    return {"subject_id": subject_id, "erased": erased}


@router.post("/dsar/restriction/{subject_id}")
async def restrict_subject(
    subject_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/dsar/restriction/{subject_id} — restrict processing."""
    from anonreq.dsar.restriction import DataRestrictionService

    body = await request.json()
    cache = get_app_state(request.app).cache_manager
    assert cache is not None
    service = DataRestrictionService(db=db, cache_manager=cache)
    tenant_id = body.get("tenant_id", "default")
    await service.restrict_subject(
        tenant_id=tenant_id,
        subject_id=subject_id,
        restricted_by=body.get("restricted_by", "unknown"),
    )
    return {"subject_id": subject_id, "restricted": True}


@router.get("/dsar/restriction/{subject_id}")
async def check_subject_restriction(
    subject_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/dsar/restriction/{subject_id} — check restriction."""
    from anonreq.dsar.restriction import DataRestrictionService

    cache = get_app_state(request.app).cache_manager
    assert cache is not None
    service = DataRestrictionService(db=db, cache_manager=cache)
    restricted = await service.is_subject_restricted(subject_id)
    return {"subject_id": subject_id, "restricted": restricted}


@router.delete("/dsar/restriction/{subject_id}")
async def remove_subject_restriction(
    subject_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """DELETE /v1/governance/dsar/restriction/{subject_id} — remove restriction."""
    from anonreq.dsar.restriction import DataRestrictionService

    cache = get_app_state(request.app).cache_manager
    assert cache is not None
    service = DataRestrictionService(db=db, cache_manager=cache)
    removed = await service.remove_restriction(subject_id)
    return {"subject_id": subject_id, "removed": removed}


@router.get("/dsar/restrictions")
async def list_restricted_subjects(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/dsar/restrictions — list restricted subjects."""
    from anonreq.dsar.restriction import DataRestrictionService

    cache = get_app_state(request.app).cache_manager
    assert cache is not None
    service = DataRestrictionService(db=db, cache_manager=cache)
    subjects = await service.list_restricted_subjects()
    return {"object": "list", "data": subjects}
