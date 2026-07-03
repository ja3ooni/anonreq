"""Tenant usage query endpoint.

Provides:
- GET /v1/admin/tenants/{tenant_id}/usage — current-period usage counters
  for RPM, TPM, concurrent requests, and daily/monthly spend
  (RBAC: OPERATOR minimum role, tenant-scoped)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from anonreq.middleware.rbac import Role, require_role

router = APIRouter(dependencies=[Depends(require_role(Role.OPERATOR))])


@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    request: Request,
    tenant_id: str,
):
    """Return current-period usage counters for the specified tenant."""
    # RBAC scope enforcement:
    # Operators can only query their own tenant.
    principal = getattr(request.state, "role_principal", {})
    user_role = principal.get("role")
    user_tenant = principal.get("tenant_id")

    if user_role != Role.ADMINISTRATOR and user_tenant != tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "reason": "tenant_scope_violation",
                "message": "Operators can only access their own tenant's usage",
            },
        )

    # Get controllers from app state
    spend_controller = getattr(request.app.state, "spend_controller", None)
    usage_limiter = getattr(request.app.state, "usage_limiter", None)

    if spend_controller is None or usage_limiter is None:
        raise HTTPException(
            status_code=503,
            detail="Usage services not available",
        )

    # Load usage metrics
    usage_record = await spend_controller.get_usage(tenant_id)
    current_counters = await usage_limiter.get_current(tenant_id)

    # Merge current rate limit counters into the UsageRecord
    usage_record.rpm_current = current_counters.get("rpm", 0)
    usage_record.tpm_current = current_counters.get("tpm", 0)
    usage_record.concurrent_current = current_counters.get("concurrent", 0)

    # Convert Decimal values to float for JSON compatibility
    usage_dump = usage_record.model_dump()
    usage_dump["daily_spend"] = float(usage_dump["daily_spend"])
    usage_dump["monthly_spend"] = float(usage_dump["monthly_spend"])

    return {
        "tenant_id": tenant_id,
        "usage": usage_dump,
        "reset_at": usage_record.reset_at.isoformat(),
    }
