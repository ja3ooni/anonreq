"""Admin API routes for DORA incident management (D-016, D-017, D-018).

Provides CRUD operations for DORA ICT incidents and SLO breach
auto-escalation hooks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from anonreq.governance.incidents import IncidentManager
from anonreq.middleware.rbac import require_role
from anonreq.models.governance import IncidentRecord, ServiceCriticality

router = APIRouter(prefix="/incidents", tags=["admin-incidents"])


class CreateIncidentRequestSchema(BaseModel):
    """Request body for creating an incident manually."""
    tenant_id: str
    service_id: str
    service_name: str
    criticality: ServiceCriticality
    severity: str
    title: str
    description: str

    model_config = {"extra": "ignore"}


class ResolveIncidentRequestSchema(BaseModel):
    """Request body for resolving an incident."""
    resolution: str


@router.get("")
async def list_incidents(
    tenant_id: str | None = Query(None),
    status: str | None = Query(None),
    criticality: ServiceCriticality | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_role("admin")),
) -> list[IncidentRecord]:
    """List incidents with optional filtering."""
    manager = IncidentManager()
    return await manager.list_incidents(
        tenant_id=tenant_id,
        status=status,
        criticality=criticality,
        skip=skip,
        limit=limit,
    )


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    _: None = Depends(require_role("admin")),
) -> IncidentRecord:
    """Get a single incident by ID."""
    manager = IncidentManager()
    incidents = await manager.list_incidents()
    for inc in incidents:
        if inc.id == incident_id:
            return inc
    raise HTTPException(status_code=404, detail="Incident not found")


@router.post("")
async def create_incident_manual(
    request: CreateIncidentRequestSchema,
    _: None = Depends(require_role("admin")),
) -> IncidentRecord:
    """Create an incident manually."""
    manager = IncidentManager()
    incident = await manager.create_incident(
        tenant_id=request.tenant_id,
        service_id=request.service_id,
        service_name=request.service_name,
        criticality=request.criticality,
        severity=request.severity,
        title=request.title,
        description=request.description,
    )
    return incident


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: ResolveIncidentRequestSchema,
    _: None = Depends(require_role("admin")),
) -> IncidentRecord:
    """Resolve an incident."""
    manager = IncidentManager()
    incident = await manager.resolve_incident(incident_id, request.resolution)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
