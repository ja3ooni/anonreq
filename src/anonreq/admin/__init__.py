"""Admin API package.

Provides:
- RBAC-secured policy management endpoints (GET/PUT /v1/admin/policies)
- Tenant usage query endpoint (GET /v1/admin/tenants/{tenant_id}/usage)
- Custom detection rules hot-reload (GET /v1/config/rules, POST /v1/admin/config/rules)

Authentication:
- Gateway API key required for all routes (applied at app level)
- Admin API key required for admin routes (via ANONREQ_ADMIN_API_KEY)
- RBAC role enforcement per endpoint via require_role dependency
"""

from anonreq.admin.router import admin_router

__all__ = ["admin_router"]
