"""Per-tenant model and provider allow-lists.

``TenantProfile.allowed_models`` and ``allowed_providers`` were stored but never
checked. An empty list means "no restriction", which keeps existing
single-tenant deployments working unchanged. The check runs before detection
and before any provider call, so a rejected request forwards nothing.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from anonreq.routing.alias_registry import AliasNotFoundError
from anonreq.state import get_app_state


def enforce_tenant_model_policy(request: Request, requested_model: str) -> None:
    """Raise HTTP 403 if the tenant may not use the requested model or provider."""
    profile = getattr(request.state, "tenant_profile", None)
    if profile is None or not (profile.allowed_models or profile.allowed_providers):
        return

    alias_registry = get_app_state(request.app).alias_registry
    if alias_registry is None:
        raise HTTPException(status_code=503, detail="Alias registry not initialized")
    try:
        alias = alias_registry.resolve(requested_model)
    except AliasNotFoundError:
        return  # the normal request path rejects unknown models with 400

    if profile.allowed_models and requested_model not in profile.allowed_models and (
        alias.model not in profile.allowed_models
    ):
        raise HTTPException(status_code=403, detail="Model not allowed for this tenant")
    if profile.allowed_providers and alias.provider not in profile.allowed_providers:
        raise HTTPException(status_code=403, detail="Provider not allowed for this tenant")
