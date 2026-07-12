"""Policy CRUD admin endpoints.

Provides:
- GET  /v1/admin/policies — list policies for the authenticated tenant
  (RBAC: OPERATOR minimum role)
- PUT  /v1/admin/policies/{policy_id} — create or update a policy rule
  (RBAC: ADMINISTRATOR minimum role)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from anonreq.middleware.rbac import Role, require_role
from anonreq.policy.models import PolicyAction, PolicyRule

router = APIRouter(dependencies=[Depends(require_role(Role.OPERATOR))])


async def _get_policy_store(request: Request) -> Any:
    """Retrieve the PolicyStore from application state."""
    store = getattr(request.app.state, "policy_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Policy store not available")
    return store


def _principal_tenant(request: Request) -> str | None:
    """Extract the tenant_id from the request's role principal.

    Admin (*) can access any tenant. Other principals are scoped to
    their own tenant.
    """
    principal = getattr(request.state, "role_principal", {})
    pt = principal.get("tenant_id")
    if pt == "*":
        return None  # None = no tenant scoping (admin)
    return pt


@router.get("/policies")
async def list_policies(
    request: Request,
    enabled: bool | None = None,
    store=Depends(_get_policy_store),
    _=Depends(require_role(Role.OPERATOR)),
) -> Any:
    tenant_id = _principal_tenant(request) or "default"

    all_rules = await store.load_policies(tenant_id)
    if enabled is not None:
        all_rules = [r for r in all_rules if r.enabled == enabled]

    # Serialize rules to dicts
    rules_data = [r.model_dump() for r in all_rules]
    for r in rules_data:
        if r.get("conditions") is None:
            r["conditions"] = {}
        if r.get("description") is None:
            r["description"] = ""

    return {
        "policies": rules_data,
        "total": len(rules_data),
        "version": "v0",
    }


@router.put("/policies/{policy_id}")
async def update_policy(
    request: Request,
    policy_id: str,
    store=Depends(_get_policy_store),
    _=Depends(require_role(Role.ADMINISTRATOR)),
) -> Any:
    """Create or update a policy rule (upsert).

    Args:
        request: FastAPI request (used for tenant scoping).
        policy_id: The rule ID from the URL path.
        store: The PolicyStore instance.

    Returns:
        Dict with the created/updated policy, new version, and status.

    Raises:
        HTTPException 422: If the request body is invalid.
    """
    tenant_id = _principal_tenant(request) or "default"

    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(  # noqa: B904
            status_code=422,
            detail={"error": "validation_error", "message": "Invalid JSON body"},
        )

    # Ensure rule_id in path matches body, or set it
    raw.setdefault("rule_id", policy_id)

    # Validate required fields
    if "action" not in raw:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "details": [{"field": "action", "message": "Field required"}],
            },
        )

    # Validate action is a known PolicyAction
    try:
        PolicyAction(raw["action"])
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=422,
            detail={
                "error": "validation_error",
                "details": [
                    {
                        "field": "action",
                        "message": f"Invalid action: {raw['action']}. "
                        f"Must be one of: {[e.value for e in PolicyAction]}",
                    }
                ],
            },
        )

    # Validate priority
    priority = raw.get("priority", 0)
    if isinstance(priority, (int, float)) and priority < 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "details": [
                    {"field": "priority", "message": "Priority must be non-negative"}
                ],
            },
        )

    # Validate through Pydantic (handles extra=forbid, field types, etc.)
    try:
        rule = PolicyRule.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(  # noqa: B904
            status_code=422,
            detail={
                "error": "validation_error",
                "details": [
                    {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            },
        )

    # Check if this is a new rule or an update
    existing = await store.get_policy(policy_id, tenant_id)
    is_update = existing is not None

    if is_update:
        rule.version = existing.version + 1
    else:
        rule.version = 1

    # Persist — load current rules, replace/add, save back
    current_rules = await store.load_policies(tenant_id)
    if is_update:
        current_rules = [r for r in current_rules if r.rule_id != policy_id]
    current_rules.append(rule)
    await store.set_tenant_policy(tenant_id, current_rules)

    return {
        "policy": rule.model_dump(),
        "version": f"v{rule.version}",
        "updated": is_update,
    }
