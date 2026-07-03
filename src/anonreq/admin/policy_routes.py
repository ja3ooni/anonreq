"""Policy CRUD admin endpoints.

Provides:
- GET  /v1/admin/policies — list policies for authenticated tenant
- PUT  /v1/admin/policies/{policy_id} — create or update a policy rule
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/policies")
async def list_policies(enabled: bool | None = None):
    """List all policies for the authenticated tenant."""
    return {"policies": [], "total": 0, "version": "v0"}


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str):
    """Create or update a policy rule."""
    return {"policy": None, "version": "v0", "updated": False}
