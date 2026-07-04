"""Admin API routes for compliance reporting (D-019, D-020, D-021).

Provides:
- GET /v1/admin/compliance/report — generate framework-specific compliance report
- GET /v1/admin/compliance/report/frameworks — list supported frameworks

All endpoints require ADMINISTRATOR role per T-15-04-01 mitigation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from anonreq.governance.reports import (
    FRAMEWORKS,
    generate_compliance_report,
    list_frameworks,
)
from anonreq.middleware.rbac import require_role

router = APIRouter(
    prefix="/compliance/report",
    tags=["admin-compliance"],
    dependencies=[Depends(require_role("admin"))],
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
