"""Admin tenant API and per-tenant model/provider enforcement."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.admin.router import tenant_admin_router
from anonreq.middleware.tenant import TenantContextMiddleware
from anonreq.routing.alias_registry import AliasNotFoundError
from anonreq.state import get_app_state
from anonreq.tenant.models import TenantProfile
from anonreq.tenant.policy import enforce_tenant_model_policy
from anonreq.tenant.registry import TenantRegistry
from anonreq.tenant.store import TenantStore

ADMIN = {"Authorization": "Bearer adminkey12345678901234567890"}
GATEWAY_KEY = {"Authorization": "Bearer " + "a" * 32}


@pytest.fixture
async def client(db_url: str) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(db_url)
    app = FastAPI()
    registry = TenantRegistry("config/tenants.yaml", store=TenantStore(engine))
    app.state.tenant_registry = registry
    app.include_router(tenant_admin_router)

    @app.get("/v1/ping")
    async def ping(request: Request) -> dict:
        return {"tenant_id": request.state.tenant_id}

    app.add_middleware(TenantContextMiddleware, tenant_registry=registry)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await engine.dispose()


BODY = {"display_name": "Acme", "allowed_models": ["gpt-4o"], "allowed_providers": ["openai"]}


@pytest.mark.unit
class TestAdminTenantApi:
    async def test_requires_admin_credential(self, client: AsyncClient) -> None:
        assert (await client.get("/v1/admin/tenants")).status_code == 401
        # The gateway key must not manage tenants.
        assert (await client.get("/v1/admin/tenants", headers=GATEWAY_KEY)).status_code == 401

    async def test_needs_no_tenant_header(self, client: AsyncClient) -> None:
        assert (await client.get("/v1/admin/tenants", headers=ADMIN)).status_code == 200

    async def test_put_creates_201_then_updates_200(self, client: AsyncClient) -> None:
        first = await client.put("/v1/admin/tenants/ws-1", json=BODY, headers=ADMIN)
        assert first.status_code == 201
        assert first.json()["source"] == "database"
        again = await client.put("/v1/admin/tenants/ws-1", json=BODY, headers=ADMIN)
        assert again.status_code == 200
        assert again.json()["allowed_models"] == ["gpt-4o"]

    async def test_list_marks_seed_and_database_sources(self, client: AsyncClient) -> None:
        await client.put("/v1/admin/tenants/ws-1", json=BODY, headers=ADMIN)
        rows = {r["tenant_id"]: r["source"] for r in (await client.get("/v1/admin/tenants", headers=ADMIN)).json()["data"]}
        assert rows == {"default": "seed", "ws-1": "database"}

    async def test_seed_tenant_cannot_be_changed(self, client: AsyncClient) -> None:
        assert (await client.put("/v1/admin/tenants/default", json=BODY, headers=ADMIN)).status_code == 409
        assert (await client.post("/v1/admin/tenants/default/disable", headers=ADMIN)).status_code == 409

    async def test_disable_blocks_traffic_and_enable_restores_it(self, client: AsyncClient) -> None:
        await client.put("/v1/admin/tenants/ws-1", json=BODY, headers=ADMIN)
        tenant = {"X-AnonReq-Tenant-ID": "ws-1"}
        assert (await client.get("/v1/ping", headers=tenant)).status_code == 200

        assert (await client.post("/v1/admin/tenants/ws-1/disable", headers=ADMIN)).json()["enabled"] is False
        assert (await client.get("/v1/ping", headers=tenant)).status_code == 403

        await client.post("/v1/admin/tenants/ws-1/enable", headers=ADMIN)
        assert (await client.get("/v1/ping", headers=tenant)).status_code == 200

    async def test_unknown_tenant_404(self, client: AsyncClient) -> None:
        assert (await client.get("/v1/admin/tenants/nope", headers=ADMIN)).status_code == 404
        assert (await client.post("/v1/admin/tenants/nope/disable", headers=ADMIN)).status_code == 404

    async def test_validation(self, client: AsyncClient) -> None:
        assert (await client.put("/v1/admin/tenants/ws-1", json={"display_name": ""}, headers=ADMIN)).status_code == 422
        assert (await client.put("/v1/admin/tenants/ws-1", json={**BODY, "surprise": 1}, headers=ADMIN)).status_code == 422
        assert (await client.put("/v1/admin/tenants/bad id", json=BODY, headers=ADMIN)).status_code == 422

    async def test_new_tenant_accepted_by_middleware_without_restart(self, client: AsyncClient) -> None:
        tenant = {"X-AnonReq-Tenant-ID": "ws-live"}
        assert (await client.get("/v1/ping", headers=tenant)).status_code == 400
        await client.put("/v1/admin/tenants/ws-live", json=BODY, headers=ADMIN)
        assert (await client.get("/v1/ping", headers=tenant)).status_code == 200


class StubAliases:
    def resolve(self, name: str) -> SimpleNamespace:
        table = {"fast": ("openai", "gpt-4o-mini"), "smart": ("anthropic", "claude-x")}
        if name not in table:
            raise AliasNotFoundError(name, list(table))
        provider, model = table[name]
        return SimpleNamespace(provider=provider, model=model)


def request_for(profile: TenantProfile | None) -> Request:
    app = FastAPI()
    get_app_state(app).alias_registry = StubAliases()
    request = Request({"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"})
    if profile is not None:
        request.state.tenant_profile = profile
    return request


def tenant(**kw: object) -> TenantProfile:
    return TenantProfile(tenant_id="t", display_name="T", **kw)  # type: ignore[arg-type]


@pytest.mark.unit
class TestModelPolicy:
    def test_unrestricted_tenant_passes(self) -> None:
        enforce_tenant_model_policy(request_for(tenant()), "smart")

    def test_no_tenant_profile_passes(self) -> None:
        enforce_tenant_model_policy(request_for(None), "smart")

    def test_allowed_by_alias_name_or_resolved_model(self) -> None:
        enforce_tenant_model_policy(request_for(tenant(allowed_models=["fast"])), "fast")
        enforce_tenant_model_policy(request_for(tenant(allowed_models=["gpt-4o-mini"])), "fast")

    def test_model_outside_list_is_403(self) -> None:
        with pytest.raises(HTTPException) as err:
            enforce_tenant_model_policy(request_for(tenant(allowed_models=["fast"])), "smart")
        assert err.value.status_code == 403

    def test_provider_outside_list_is_403(self) -> None:
        with pytest.raises(HTTPException) as err:
            enforce_tenant_model_policy(request_for(tenant(allowed_providers=["openai"])), "smart")
        assert err.value.status_code == 403

    def test_unknown_alias_is_left_to_the_normal_400_path(self) -> None:
        enforce_tenant_model_policy(request_for(tenant(allowed_models=["fast"])), "mystery")
