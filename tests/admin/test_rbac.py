"""Tests for RBAC middleware with role hierarchy enforcement.

Tests the require_role FastAPI dependency that verifies the authenticated
principal has sufficient role for the requested operation.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from anonreq.middleware.rbac import Role, require_role


def _make_app_with_principal(role: str | None = None) -> FastAPI:
    """Create a test app with RBAC-protected endpoints and optional principal.

    Args:
        role: The role to set in request state, or None for unauthenticated.

    Returns:
        A configured FastAPI app ready for TestClient.
    """
    app = FastAPI()

    @app.get("/test/admin")
    async def admin_endpoint(_=Depends(require_role(Role.ADMINISTRATOR))):
        return {"status": "ok"}

    @app.get("/test/operator")
    async def operator_endpoint(_=Depends(require_role(Role.OPERATOR))):
        return {"status": "ok"}

    @app.get("/test/security_officer")
    async def security_officer_endpoint(_=Depends(require_role(Role.SECURITY_OFFICER))):
        return {"status": "ok"}

    @app.get("/test/read_only_auditor")
    async def readonly_endpoint(_=Depends(require_role(Role.READ_ONLY_AUDITOR))):
        return {"status": "ok"}

    if role is not None:
        @app.middleware("http")
        async def inject_principal(request, call_next):
            request.state.role_principal = {
                "principal_id": "test_user",
                "role": role,
                "tenant_id": "test_tenant",
            }
            return await call_next(request)

    return app


class TestRequireRole:
    def test_admin_allows_admin_role(self):
        """require_role(ADMINISTRATOR) allows requests with admin role."""
        app = _make_app_with_principal("administrator")
        client = TestClient(app)
        response = client.get("/test/admin")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_admin_denies_operator_role(self):
        """require_role(ADMINISTRATOR) denies requests with operator role."""
        app = _make_app_with_principal("operator")
        client = TestClient(app)
        response = client.get("/test/admin")
        assert response.status_code == 403

    def test_operator_allows_admin_or_operator(self):
        """require_role(OPERATOR) allows requests with admin or operator role."""
        for role in ("administrator", "operator"):
            app = _make_app_with_principal(role)
            client = TestClient(app)
            response = client.get("/test/operator")
            assert response.status_code == 200, f"Failed for role {role}"

    def test_missing_role_raises_403(self):
        """Missing role raises HTTP 403 with structured error body."""
        app = _make_app_with_principal("read_only_auditor")
        client = TestClient(app)
        response = client.get("/test/admin")
        assert response.status_code == 403
        body = response.json()
        # FastAPI wraps HTTPException detail in {"detail": ...}
        detail = body.get("detail", body)
        assert "error" in detail
        assert detail["error"] == "forbidden"

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated request raises HTTP 401 before RBAC check."""
        app = _make_app_with_principal(None)  # No principal set
        client = TestClient(app)
        response = client.get("/test/admin")
        assert response.status_code == 401

    def test_roles_are_hierarchical(self):
        """Roles are hierarchical: admin > security_officer > operator > read_only_auditor."""
        test_cases = [
            ("administrator", "admin", True),
            ("administrator", "operator", True),
            ("administrator", "read_only_auditor", True),
            ("administrator", "security_officer", True),
            ("security_officer", "admin", False),
            ("security_officer", "operator", True),
            ("security_officer", "read_only_auditor", True),
            ("security_officer", "security_officer", True),
            ("operator", "admin", False),
            ("operator", "operator", True),
            ("operator", "read_only_auditor", True),
            ("operator", "security_officer", False),
            ("read_only_auditor", "admin", False),
            ("read_only_auditor", "operator", False),
            ("read_only_auditor", "read_only_auditor", True),
            ("read_only_auditor", "security_officer", False),
        ]
        for user_role, endpoint, should_pass in test_cases:
            app = _make_app_with_principal(user_role)
            client = TestClient(app)
            response = client.get(f"/test/{endpoint}")
            if should_pass:
                assert response.status_code == 200, (
                    f"Role '{user_role}' should pass '{endpoint}' but got {response.status_code}"
                )
            else:
                assert response.status_code == 403, (
                    f"Role '{user_role}' should fail '{endpoint}' but got {response.status_code}"
                )

    def test_rbac_dependency_is_injectable_for_testing(self):
        """RBAC dependency can be overridden for test flexibility."""
        app = FastAPI()
        rbac_check = require_role(Role.ADMINISTRATOR)

        @app.get("/test/admin")
        async def admin_endpoint(_=Depends(rbac_check)):
            return {"status": "ok"}

        # Inject a read_only_auditor principal (would normally fail without override)
        @app.middleware("http")
        async def inject_principal(request, call_next):
            request.state.role_principal = {
                "principal_id": "test_user",
                "role": "read_only_auditor",
                "tenant_id": "test_tenant",
            }
            return await call_next(request)

        # Override with a no-op that bypasses RBAC
        app.dependency_overrides[rbac_check] = lambda: None
        client = TestClient(app)
        response = client.get("/test/admin")
        assert response.status_code == 200
