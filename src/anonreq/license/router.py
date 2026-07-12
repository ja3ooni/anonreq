"""FastAPI router for administrative license actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from anonreq.license.models import LicenseStatus
from anonreq.license.validator import LicenseValidator


async def _admin_auth(request: "Request") -> None:
    """Lazy-import require_auth to avoid circular dependency."""
    from anonreq.admin.router import require_auth

    return await require_auth(request)


router = APIRouter(
    prefix="/v1/admin/license",
    tags=["admin-license"],
    dependencies=[Depends(_admin_auth)],
)


@router.get("", response_model=LicenseStatus)
async def get_license_status() -> LicenseStatus:
    """GET /v1/admin/license — retrieve current license status.

    Returns the decoded organization, tier, allowed features, and expiration status.
    """
    return await LicenseValidator.get_status()
