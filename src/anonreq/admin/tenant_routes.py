"""Admin tenant registry endpoints.

- GET  /v1/admin/tenants                 — list tenants (seed and database)
- GET  /v1/admin/tenants/{tenant_id}     — read one tenant
- PUT  /v1/admin/tenants/{tenant_id}     — create or update (idempotent upsert)
- POST /v1/admin/tenants/{tenant_id}/disable
- POST /v1/admin/tenants/{tenant_id}/enable

Tenants defined in ``config/tenants.yaml`` are read-only here (409). Tenants are
never deleted, only disabled, so audit history keeps resolving. All endpoints
require ADMINISTRATOR. These routes are exempt from the ``X-AnonReq-Tenant-ID``
header requirement because they manage tenants rather than act as one.
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from anonreq.middleware.rbac import Role, require_role
from anonreq.tenant.models import TenantProfile
from anonreq.tenant.registry import SeedTenantError, TenantRegistry
from anonreq.tenant.store import TENANT_ID_PATTERN, TenantStoreError

logger = structlog.get_logger("anonreq.admin.tenants")

router = APIRouter(dependencies=[Depends(require_role(Role.ADMINISTRATOR))])

_TENANT_ID_PATH = Path(pattern=TENANT_ID_PATTERN.pattern, max_length=64)


class TenantUpsertRequest(BaseModel):
    """Body for ``PUT /v1/admin/tenants/{tenant_id}``. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=256)
    enabled: bool = True
    kms_key_arn: str | None = Field(default=None, max_length=512)
    spend_limits: dict[str, Any] = Field(default_factory=dict)
    rate_limits: dict[str, Any] = Field(default_factory=dict)
    allowed_providers: list[str] = Field(default_factory=list, max_length=64)
    allowed_models: list[str] = Field(default_factory=list, max_length=256)


def _registry(request: Request) -> TenantRegistry:
    registry = getattr(request.app.state, "tenant_registry", None)
    if registry is None or not registry.has_store:
        raise HTTPException(status_code=503, detail="Tenant registry database not configured")
    return cast(TenantRegistry, registry)


def _view(profile: TenantProfile, source: str) -> dict[str, Any]:
    return {
        "tenant_id": profile.tenant_id,
        "display_name": profile.display_name,
        "enabled": profile.enabled,
        "source": source,
        "kms_key_arn": profile.kms_key_arn,
        "spend_limits": profile.spend_limits,
        "rate_limits": profile.rate_limits,
        "allowed_providers": profile.allowed_providers,
        "allowed_models": profile.allowed_models,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


def _source(registry: TenantRegistry, tenant_id: str) -> str:
    return "seed" if registry.is_seed(tenant_id) else "database"


@router.get("/tenants")
async def list_tenants(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    try:
        rows = await registry.list_with_source()
    except TenantStoreError as exc:
        raise HTTPException(status_code=503, detail="Tenant registry unavailable") from exc
    return {"object": "list", "data": [_view(p, src) for p, src in rows]}


@router.get("/tenants/{tenant_id}")
async def get_tenant(request: Request, tenant_id: str = _TENANT_ID_PATH) -> dict[str, Any]:
    registry = _registry(request)
    try:
        profile = await registry.aget(tenant_id)
    except TenantStoreError as exc:
        raise HTTPException(status_code=503, detail="Tenant registry unavailable") from exc
    if profile is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _view(profile, _source(registry, tenant_id))


@router.put("/tenants/{tenant_id}")
async def upsert_tenant(
    request: Request,
    response: Response,
    body: TenantUpsertRequest,
    tenant_id: str = _TENANT_ID_PATH,
) -> dict[str, Any]:
    registry = _registry(request)
    profile = TenantProfile(tenant_id=tenant_id, **body.model_dump())
    try:
        stored, created = await registry.upsert(profile)
    except SeedTenantError as exc:
        raise HTTPException(status_code=409, detail="Tenant is defined in the YAML seed") from exc
    except TenantStoreError as exc:
        raise HTTPException(status_code=503, detail="Tenant registry unavailable") from exc
    response.status_code = 201 if created else 200
    logger.info("tenant.upserted", tenant_id=tenant_id, created=created, enabled=stored.enabled)
    return _view(stored, "database")


@router.post("/tenants/{tenant_id}/disable")
async def disable_tenant(request: Request, tenant_id: str = _TENANT_ID_PATH) -> dict[str, Any]:
    return await _set_enabled(request, tenant_id, False)


@router.post("/tenants/{tenant_id}/enable")
async def enable_tenant(request: Request, tenant_id: str = _TENANT_ID_PATH) -> dict[str, Any]:
    return await _set_enabled(request, tenant_id, True)


async def _set_enabled(request: Request, tenant_id: str, enabled: bool) -> dict[str, Any]:
    registry = _registry(request)
    try:
        stored = await registry.set_enabled(tenant_id, enabled)
    except SeedTenantError as exc:
        raise HTTPException(status_code=409, detail="Tenant is defined in the YAML seed") from exc
    except TenantStoreError as exc:
        raise HTTPException(status_code=503, detail="Tenant registry unavailable") from exc
    if stored is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    logger.info("tenant.enabled_changed", tenant_id=tenant_id, enabled=enabled)
    return _view(stored, "database")
