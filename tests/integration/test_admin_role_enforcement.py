"""Integration tests for canonical admin role enforcement."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anonreq.admin.router import admin_router


class _ProviderInventoryStub:
    async def list_providers(self, **_kwargs):
        return []

    async def get_provider_record(self, _provider_id: str):
        return None

    async def suspend_provider(self, **_kwargs):
        return SimpleNamespace(model_dump=lambda: {})

    async def unsuspend_provider(self, **_kwargs):
        return SimpleNamespace(model_dump=lambda: {})

    async def flag_concentration_risk(self, **_kwargs):
        return SimpleNamespace(model_dump=lambda: {})


@pytest.fixture
def app():
    app = FastAPI()
    app.state.provider_inventory = _ProviderInventoryStub()

    @app.middleware("http")
    async def inject_principal(request, call_next):
        role = request.headers.get("X-Test-Role", "administrator")
        request.state.role_principal = {
            "principal_id": "test-user",
            "role": role,
            "tenant_id": "test-tenant",
        }
        return await call_next(request)

    app.include_router(admin_router)
    return app


def test_read_only_auditor_is_blocked_from_admin_only_routes(app):
    client = TestClient(app)
    headers = {
        "Authorization": "Bearer adminkey12345678901234567890",
        "X-Test-Role": "read_only_auditor",
    }

    response = client.get("/v1/admin/providers", headers=headers)
    assert response.status_code == 403

    response = client.get("/v1/admin/compliance/report/frameworks", headers=headers)
    assert response.status_code == 403

    response = client.get("/v1/admin/incidents", headers=headers)
    assert response.status_code == 403


def test_administrator_can_access_admin_only_routes(app):
    client = TestClient(app)
    headers = {
        "Authorization": "Bearer adminkey12345678901234567890",
        "X-Test-Role": "administrator",
    }

    response = client.get("/v1/admin/providers", headers=headers)
    assert response.status_code == 200

    response = client.get("/v1/admin/compliance/report/frameworks", headers=headers)
    assert response.status_code == 200

    response = client.get("/v1/admin/incidents", headers=headers)
    assert response.status_code == 200
