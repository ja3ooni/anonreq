"""Bind audit reads to the caller's tenant.

The legacy admin API key is not stored against a tenant. ``verify_admin_api_key``
and the admin router's API-key fallback set the principal ``tenant_id`` to
``"*"``. That wildcard means the credential is not tenant-bound. It is never
permission to read every tenant. For a ``"*"`` principal the tenant comes from
the ``X-AnonReq-Tenant-ID`` header, after ``TenantContextMiddleware`` has
checked it against the tenant registry and copied it to
``request.state.tenant_id``. Any holder of that key can still choose a tenant
by sending a different header.

A concrete OIDC (or test) ``tenant_id`` is stronger than the header, because
the caller cannot swap the claim per request. Binding the key itself to a
tenant is tracked in https://github.com/ja3ooni/anonreq/issues/7.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

_WILDCARD_TENANT = "*"
_MISMATCH_DETAIL = "tenant_id does not match the caller tenant"
_MISSING_DETAIL = "Caller tenant could not be determined"


def _concrete_tenant(value: object) -> str | None:
    """Return a usable tenant id, or None for missing, blank, or wildcard."""
    if not isinstance(value, str):
        return None
    tenant = value.strip()
    if not tenant or tenant == _WILDCARD_TENANT or len(tenant) > 64:
        return None
    if any(ord(char) < 32 or char == "\x7f" for char in tenant):
        return None
    return tenant


def concrete_request_tenant(request: Request) -> str | None:
    """Tenant for an API key: middleware state, else ``X-AnonReq-Tenant-ID``.

    A wildcard is never returned. When the header and the validated state
    name different tenants, neither is trusted.
    """
    state_tenant = _concrete_tenant(getattr(request.state, "tenant_id", None))
    header_tenant = _concrete_tenant(request.headers.get("X-AnonReq-Tenant-ID"))
    if state_tenant and header_tenant and state_tenant != header_tenant:
        return None
    return state_tenant or header_tenant


def narrow_wildcard_principal(request: Request) -> None:
    """Replace a wildcard or blank principal tenant with this request's tenant.

    A concrete tenant already on the principal is left alone. ``"*"`` is
    never kept: it is not permission to read every tenant.
    """
    principal = getattr(request.state, "role_principal", None)
    if not isinstance(principal, dict):
        return
    if _concrete_tenant(principal.get("tenant_id")):
        return
    tenant = concrete_request_tenant(request)
    principal["tenant_id"] = tenant or ""


def _principal_tenant(principal: object) -> str | None:
    if not isinstance(principal, dict):
        return None
    return _concrete_tenant(principal.get("tenant_id"))


def caller_tenant(request: Request) -> str | None:
    """Strongest tenant already attached to this request, if any.

    Order:

    1. ``request.state.role_principal["tenant_id"]`` when it names one tenant.
    2. ``request.state.oidc_principal["tenant_id"]`` on the same rule, when the
       role principal is absent or only carries the unbound wildcard.
    3. ``request.state.tenant_id`` from ``X-AnonReq-Tenant-ID``. This is the
       fallback when the principal is missing or is the legacy ``"*"`` admin
       key. See https://github.com/ja3ooni/anonreq/issues/7.
    """
    role_tenant = _principal_tenant(getattr(request.state, "role_principal", None))
    if role_tenant is not None:
        return role_tenant
    oidc_tenant = _principal_tenant(getattr(request.state, "oidc_principal", None))
    if oidc_tenant is not None:
        return oidc_tenant
    return _concrete_tenant(getattr(request.state, "tenant_id", None))


def resolve_scoped_tenant(request: Request, requested_tenant_id: str | None) -> str:
    """Return the tenant this caller may read.

    A supplied ``tenant_id`` that is not the caller tenant is rejected with
    HTTP 403. Omitting it scopes the query to the caller tenant. There is no
    path that lists every tenant.
    """
    narrow_wildcard_principal(request)
    tenant = caller_tenant(request)
    if tenant is None:
        raise HTTPException(status_code=403, detail=_MISSING_DETAIL)
    if requested_tenant_id is None:
        return tenant
    requested = requested_tenant_id.strip()
    if not requested or requested == tenant:
        return tenant
    raise HTTPException(status_code=403, detail=_MISMATCH_DETAIL)
