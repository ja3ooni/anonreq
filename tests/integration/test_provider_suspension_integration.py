"""Provider suspension integration tests at HTTP route level.

Covers:
- POST /v1/admin/providers/{id}/suspend returns 200 and suspended status
- POST /v1/admin/providers/{id}/unsuspend returns 200 and active status
- POST /v1/admin/providers/{id}/suspend for missing provider returns 404
- Suspend state persists across list/get operations
- Fail-secure: unknown provider is_provider_active returns False
- Suspension can't be bypassed — check_provider_active raises ValueError
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anonreq.admin.router import admin_router
from anonreq.models.governance import ProviderRecord

_ADMIN_AUTH_KEY = os.environ.get(
    "ANONREQ_ADMIN_API_KEY", "adminkey12345678901234567890"
)


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {_ADMIN_AUTH_KEY}"}


def _make_provider_record(
    provider_id: str = "prov_test_001",
    name: str = "Test Provider",
    status: str = "active",
) -> ProviderRecord:
    now = datetime.now(UTC)
    return ProviderRecord(
        id=provider_id,
        name=name,
        provider_type="llm",
        status=status,
        dora_ict_critical=False,
        concentration_risk=False,
        review_cycle_days=365,
        created_at=now,
        updated_at=now,
    )


def _make_test_app(
    role: str = "administrator",
    inventory: AsyncMock | None = None,
) -> FastAPI:
    """Create a FastAPI app with the admin router and mock provider inventory.

    Args:
        role: The RBAC role to assign.
        inventory: Pre-configured mock ProviderInventory. If None, creates
            a default mock.

    Returns:
        A configured FastAPI app ready for TestClient.
    """
    app = FastAPI()

    if inventory is None:
        inventory = AsyncMock()
        # Default: provider exists and is active
        active_record = _make_provider_record(status="active")
        inventory.get_provider_record.return_value = active_record
        inventory.suspend_provider.return_value = _make_provider_record(
            status="suspended"
        )
        inventory.unsuspend_provider.return_value = _make_provider_record(
            status="active"
        )
        inventory.list_providers.return_value = [active_record]

    app.state.provider_inventory = inventory

    @app.middleware("http")
    async def inject_principal(request, call_next):
        request.state.role_principal = {
            "principal_id": "test_admin",
            "role": role,
            "tenant_id": "*",
        }
        return await call_next(request)

    app.include_router(admin_router)
    return app


# ── Suspend ───────────────────────────────────────────────────────


class TestSuspendEndpoint:
    """Tests for POST /v1/admin/providers/{id}/suspend."""

    def test_suspend_returns_200_and_suspended_status(self):
        """Suspend endpoint returns 200 with status='suspended'."""
        mock_inventory = AsyncMock()
        mock_inventory.suspend_provider.return_value = _make_provider_record(
            status="suspended"
        )
        app = _make_test_app(inventory=mock_inventory)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/prov_test_001/suspend",
            json={"reason": "Security incident", "suspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "suspended"

    def test_suspend_returns_404_for_missing_provider(self):
        """Suspend returns 404 for nonexistent provider."""
        mock_inventory = AsyncMock()
        mock_inventory.suspend_provider.side_effect = ValueError("Provider not found")
        app = _make_test_app(inventory=mock_inventory)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/nonexistent/suspend",
            json={"reason": "test", "suspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 404

    def test_suspend_requires_administrator_role(self):
        """OPERATOR role cannot suspend (requires ADMINISTRATOR)."""
        app = _make_test_app(role="operator")
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/prov_test_001/suspend",
            json={"reason": "test", "suspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 403

    def test_suspend_returns_401_without_auth(self):
        """Request without admin API key returns 401."""
        app = _make_test_app()
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/prov_test_001/suspend",
            json={"reason": "test", "suspended_by": "admin"},
        )
        assert response.status_code == 401


# ── Unsuspend ─────────────────────────────────────────────────────


class TestUnsuspendEndpoint:
    """Tests for POST /v1/admin/providers/{id}/unsuspend."""

    def test_unsuspend_returns_200_and_active_status(self):
        """Unsuspend endpoint returns 200 with status='active'."""
        mock_inventory = AsyncMock()
        mock_inventory.unsuspend_provider.return_value = _make_provider_record(
            status="active"
        )
        app = _make_test_app(inventory=mock_inventory)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/prov_test_001/unsuspend",
            json={"unsuspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"

    def test_unsuspend_returns_404_for_missing_provider(self):
        """Unsuspend returns 404 for nonexistent provider."""
        mock_inventory = AsyncMock()
        mock_inventory.unsuspend_provider.side_effect = ValueError(
            "Provider not found"
        )
        app = _make_test_app(inventory=mock_inventory)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/nonexistent/unsuspend",
            json={"unsuspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 404

    def test_unsuspend_requires_administrator_role(self):
        """OPERATOR role cannot unsuspend."""
        app = _make_test_app(role="operator")
        client = TestClient(app)

        response = client.post(
            "/v1/admin/providers/prov_test_001/unsuspend",
            json={"unsuspended_by": "admin"},
            headers=_auth_header(),
        )
        assert response.status_code == 403


# ── State persistence (via list_providers) ────────────────────────


class TestProviderListAfterSuspension:
    """Verify list_providers reflects suspension state."""

    def test_list_shows_active_and_suspended_providers(self):
        """GET /providers returns providers with their current status."""
        mock_inventory = AsyncMock()
        mock_inventory.list_providers.return_value = [
            _make_provider_record(
                provider_id="prov_active", name="Active Provider", status="active"
            ),
            _make_provider_record(
                provider_id="prov_suspended",
                name="Suspended Provider",
                status="suspended",
            ),
        ]
        app = _make_test_app(inventory=mock_inventory)
        client = TestClient(app)

        response = client.get(
            "/v1/admin/providers",
            headers=_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["object"] == "list"
        statuses = {p["id"]: p["status"] for p in body["data"]}
        assert statuses["prov_active"] == "active"
        assert statuses["prov_suspended"] == "suspended"


# ── is_provider_active fail-secure ────────────────────────────────


class TestIsProviderActive:
    """Verify is_provider_active fail-secure behavior."""

    @pytest.mark.asyncio
    async def test_active_returns_true(self):
        """Active provider returns True."""
        from anonreq.governance.provider_inventory import ProviderInventory
        from anonreq.models.governance import ProviderRecord

        inv = ProviderInventory(
            db=AsyncMock(),
            lifecycle_manager=AsyncMock(),
        )
        active = ProviderRecord(
            name="Test", provider_type="llm", status="active"
        )
        inv.get_provider_record = AsyncMock(return_value=active)

        result = await inv.is_provider_active("prov_001")
        assert result is True

    @pytest.mark.asyncio
    async def test_suspended_returns_false(self):
        """Suspended provider returns False."""
        from anonreq.governance.provider_inventory import ProviderInventory

        inv = ProviderInventory(
            db=AsyncMock(),
            lifecycle_manager=AsyncMock(),
        )
        suspended = ProviderRecord(
            name="Test", provider_type="llm", status="suspended"
        )
        inv.get_provider_record = AsyncMock(return_value=suspended)

        result = await inv.is_provider_active("prov_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_returns_false_fail_secure(self):
        """Unknown provider returns False (fail-secure)."""
        from anonreq.governance.provider_inventory import ProviderInventory

        inv = ProviderInventory(db=AsyncMock(), lifecycle_manager=AsyncMock())
        inv.get_provider_record = AsyncMock(return_value=None)

        result = await inv.is_provider_active("unknown")
        assert result is False, "Unknown provider must return False (fail-secure)"

    @pytest.mark.asyncio
    async def test_check_provider_active_raises_for_suspended(self):
        """check_provider_active raises ValueError for suspended."""
        from anonreq.governance.provider_inventory import ProviderInventory

        inv = ProviderInventory(db=AsyncMock(), lifecycle_manager=AsyncMock())
        inv.is_provider_active = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="not active"):
            await inv.check_provider_active("prov_001")

    @pytest.mark.asyncio
    async def test_check_provider_active_passes_for_active(self):
        """check_provider_active passes without error for active."""
        from anonreq.governance.provider_inventory import ProviderInventory

        inv = ProviderInventory(db=AsyncMock(), lifecycle_manager=AsyncMock())
        inv.is_provider_active = AsyncMock(return_value=True)

        # Should not raise
        await inv.check_provider_active("prov_001")
