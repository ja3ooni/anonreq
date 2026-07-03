"""Tests for tenant usage query endpoint.

Tests cover:
- GET /v1/admin/tenants/{tenant_id}/usage returns UsageRecord
- Response includes rpm_current, tpm_current, concurrent_current
- OPERATOR can query own tenant, ADMIN can query any
- Unknown tenant returns zeros
- Unauthenticated access returns 401
"""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anonreq.admin.router import admin_router
from anonreq.policy.models import UsageRecord

_ADMIN_AUTH_KEY = os.environ.get(
    "ANONREQ_ADMIN_API_KEY", "adminkey12345678901234567890"
)


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {_ADMIN_AUTH_KEY}"}


def _make_usage_test_app(role: str = "administrator", counters: dict | None = None) -> FastAPI:
    """Create a test app with mocked SpendController and UsageLimiter.

    Args:
        role: The role for the authenticated principal.
        counters: Optional dict of counter values (rpm, tpm, concurrent).

    Returns:
        A configured FastAPI app ready for TestClient.
    """
    from datetime import datetime, timezone

    app = FastAPI()

    c = counters or {"rpm": 42, "tpm": 5000, "concurrent": 3}

    # Mock SpendController
    mock_spend = AsyncMock()
    now = datetime.now(timezone.utc)
    async def mock_get_usage(t_id: str) -> UsageRecord:
        if t_id == "test_tenant":
            return UsageRecord(
                tenant_id="test_tenant",
                rpm_current=c["rpm"],
                tpm_current=c["tpm"],
                concurrent_current=c["concurrent"],
                daily_spend=Decimal("12.50"),
                monthly_spend=Decimal("350.00"),
                reset_at=now,
            )
        return UsageRecord(
            tenant_id=t_id,
            rpm_current=0,
            tpm_current=0,
            concurrent_current=0,
            daily_spend=Decimal("0"),
            monthly_spend=Decimal("0"),
            reset_at=now,
        )
    mock_spend.get_usage.side_effect = mock_get_usage
    app.state.spend_controller = mock_spend

    # Mock UsageLimiter
    mock_limiter = AsyncMock()
    mock_limiter.get_current.return_value = c
    app.state.usage_limiter = mock_limiter

    @app.middleware("http")
    async def inject_principal(request, call_next):
        request.state.role_principal = {
            "principal_id": "test_admin",
            "role": role,
            "tenant_id": "test_tenant",
        }
        return await call_next(request)

    app.include_router(admin_router)
    return app


class TestUsageQuery:
    """Tests for GET /v1/admin/tenants/{tenant_id}/usage."""

    def test_returns_usage_record_for_valid_tenant(self):
        """GET returns usage record with all counter fields."""
        app = _make_usage_test_app()
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/test_tenant/usage", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == "test_tenant"
        usage = body["usage"]
        assert usage["rpm_current"] == 42
        assert usage["tpm_current"] == 5000
        assert usage["concurrent_current"] == 3
        assert "daily_spend" in usage
        assert "monthly_spend" in usage
        assert "reset_at" in usage

    def test_response_includes_reset_at(self):
        """Response includes reset_at timestamp for next budget window."""
        app = _make_usage_test_app()
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/test_tenant/usage", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "reset_at" in body
        assert body["reset_at"] is not None

    def test_operator_can_query_own_tenant(self):
        """OPERATOR role can query usage for their own tenant."""
        app = _make_usage_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/test_tenant/usage", headers=headers)
        assert response.status_code == 200

    def test_operator_cannot_query_other_tenant(self):
        """OPERATOR role cannot query usage for a different tenant."""
        app = _make_usage_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/other_tenant/usage", headers=headers)
        # Stub doesn't enforce tenant scoping — should return 403 with real impl
        assert response.status_code == 403

    def test_admin_can_query_any_tenant(self):
        """ADMINISTRATOR can query usage for any tenant."""
        app = _make_usage_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/any_tenant/usage", headers=headers)
        assert response.status_code == 200

    def test_read_only_cannot_query_usage(self):
        """READ_ONLY role cannot query usage (needs OPERATOR)."""
        app = _make_usage_test_app("read_only")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/test_tenant/usage", headers=headers)
        # Stub doesn't enforce RBAC — should return 403 with real impl
        assert response.status_code == 403

    def test_unknown_tenant_returns_zeros(self):
        """Unknown tenant returns usage record with zeros."""
        app = _make_usage_test_app("administrator", counters={"rpm": 0, "tpm": 0, "concurrent": 0})
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/tenants/unknown_tenant/usage", headers=headers)
        assert response.status_code == 200
        usage = response.json()["usage"]
        assert usage["rpm_current"] == 0
        assert usage["tpm_current"] == 0
        assert usage["concurrent_current"] == 0
        assert usage["daily_spend"] == 0 or usage["daily_spend"] == "0"

    def test_unauthenticated_access_returns_401(self):
        """Request without admin API key returns 401."""
        app = _make_usage_test_app()
        client = TestClient(app)
        response = client.get("/v1/admin/tenants/test_tenant/usage")
        assert response.status_code == 401
