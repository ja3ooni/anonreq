"""Admin API routes for compliance reporting (D-019, D-020, D-021).

Provides:
- GET /v1/admin/compliance/report — generate framework-specific compliance report
- GET /v1/admin/compliance/report/frameworks — list supported frameworks
- GET /v1/admin/compliance/evidence — generate compliance evidence for frameworks (Phase 26)

All endpoints require ADMINISTRATOR role per T-15-04-01 mitigation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from anonreq.governance.reports import (
    FRAMEWORKS,
    generate_compliance_report,
    list_frameworks,
)
from anonreq.license.validator import require_license
from anonreq.middleware.rbac import Role, require_role
from anonreq.services.compliance_evidence import ComplianceEvidenceService
from anonreq.state import get_app_state

router = APIRouter(
    prefix="/compliance/report",
    tags=["admin-compliance"],
    dependencies=[Depends(require_role(Role.ADMINISTRATOR))],
)

# New router for other compliance endpoints to map directly to /v1/admin/compliance
evidence_router = APIRouter(
    prefix="/compliance",
    tags=["admin-compliance"],
    dependencies=[Depends(require_role(Role.ADMINISTRATOR))],
)


@router.get("")
async def get_compliance_report(
    framework: str = Query(..., description="Framework ID (e.g. DORA, GDPR)"),
    tenant_id: str | None = Query(None, description="Optional tenant scope"),
) -> dict:
    """GET /v1/admin/compliance/report — generate a compliance report.

    Query params:
        framework (required): One of the supported framework IDs.
        tenant_id (optional): Scope report to a specific tenant.

    Returns:
        A structured compliance report with sections and evidence.
    """
    if framework.upper() not in FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported framework '{framework}'. "
            f"Supported: {', '.join(sorted(FRAMEWORKS))}",
        )
    return await generate_compliance_report(
        framework=framework.upper(),
        tenant_id=tenant_id,
    )


@router.get("/frameworks")
async def get_frameworks() -> dict:
    """GET /v1/admin/compliance/report/frameworks — list supported frameworks.

    Returns:
        A dict with framework count and list.
    """
    frameworks = await list_frameworks()
    return {
        "object": "list",
        "data": frameworks,
        "total": len(frameworks),
    }


@evidence_router.get("/evidence")
async def get_compliance_evidence(
    request: Request,
    framework: str = Query("soc2", description="Framework ID (e.g. soc2, iso27001, gdpr)"),
    _license: None = Depends(require_license("compliance_monitoring")),
) -> dict:
    """GET /v1/admin/compliance/evidence — collect compliance evidence.

    Per D-04: Aggregates evidence from SLO engine, audit chain,
    governance records, and incident history.
    """
    service: ComplianceEvidenceService = get_app_state(request.app).compliance_evidence_service
    return await service.collect_evidence(framework=framework)
