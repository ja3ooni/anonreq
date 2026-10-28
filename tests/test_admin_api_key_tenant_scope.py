"""The legacy admin API key is a tenant-scoped administrator.

The gateway (client) key is not. It gets 403 on admin routes. A missing
key is 401. The admin principal tenant is never ``"*"``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.api.v1.admin.anonymization_events import router as events_router
from anonreq.api.v1.admin.audit import router as audit_router
from anonreq.config import settings
from anonreq.services.audit_chain import AuditChainService

_OWN = "demo"
_OTHER = "other-tenant"
_ROUTES = (
    "/v1/admin/audit/config-history",
    "/v1/admin/audit/anonymization-export?format=json",
    "/v1/admin/anonymization-events",
    "/v1/admin/anonymization-events/export",
)


@pytest.fixture
def keyed_app() -> FastAPI:
    app = FastAPI()
    app.state.audit_chain = AsyncMock(spec=AuditChainService)
    app.state.audit_chain.get_events.return_value = []
    app.state.audit_chain.count_events.return_value = 0
    app.include_router(audit_router)
    app.include_router(events_router)
    return app


def _headers(token: str, tenant: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-AnonReq-Tenant-ID": tenant,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES)
async def test_admin_key_reads_own_tenant_and_rejects_another(
    keyed_app: FastAPI,
    route: str,
) -> None:
    transport = ASGITransport(app=keyed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        own = await client.get(route, headers=_headers(settings.ADMIN_API_KEY or "", _OWN))
        foreign = await client.get(
            route,
            headers=_headers(settings.ADMIN_API_KEY or "", _OWN),
            params={"tenant_id": _OTHER},
        )
        missing = await client.get(route, headers={"X-AnonReq-Tenant-ID": _OWN})
    assert own.status_code == 200, own.text
    assert foreign.status_code == 403
    assert missing.status_code == 401
    assert settings.ADMIN_API_KEY
    for call in keyed_app.state.audit_chain.get_events.await_args_list:
        assert call.kwargs.get("tenant_id") == _OWN
        assert call.kwargs.get("tenant_id") != "*"


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES)
async def test_gateway_key_is_forbidden_on_admin_routes(
    keyed_app: FastAPI,
    route: str,
) -> None:
    transport = ASGITransport(app=keyed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(route, headers=_headers(settings.API_KEY, _OWN))
    assert response.status_code == 403, response.text
    keyed_app.state.audit_chain.get_events.assert_not_called()


@pytest.fixture(autouse=True)
def _admin_key_bound_to_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """ANONREQ_ADMIN_TENANT_ID binds the admin key to _OWN on the server."""
    monkeypatch.setattr(settings, "ADMIN_TENANT_ID", _OWN)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES)
async def test_admin_key_header_for_another_tenant_is_403(
    keyed_app: FastAPI,
    route: str,
) -> None:
    """The tenant header cannot move the admin key to another tenant."""
    transport = ASGITransport(app=keyed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            route, headers=_headers(settings.ADMIN_API_KEY or "", _OTHER),
        )
    assert response.status_code == 403
    keyed_app.state.audit_chain.get_events.assert_not_awaited()
