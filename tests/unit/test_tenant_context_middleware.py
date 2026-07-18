"""Unit tests for TenantContextMiddleware.

Per D-01 through D-04, verifies header validation, tenant lookup,
disabled tenant rejection, and structlog context binding.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from anonreq.middleware.tenant import TenantContextMiddleware
from anonreq.tenant.registry import TenantRegistry


def make_app(tenant_registry: TenantRegistry) -> FastAPI:
    """Create a minimal FastAPI app with TenantContextMiddleware for testing."""
    app = FastAPI()

    @app.get("/v1/test")
    async def test_route(request: Request) -> dict:
        return {
            "tenant_id": getattr(request.state, "tenant_id", None),
            "tenant_profile": getattr(request.state, "tenant_profile", None),
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> dict:
        return {"metrics": "ok"}

    app.add_middleware(TenantContextMiddleware, tenant_registry=tenant_registry)
    return app


@pytest.mark.unit
class TestTenantContextMiddleware:
    """Tests for TenantContextMiddleware validation behavior."""

    @pytest.fixture
    def registry(self) -> TenantRegistry:
        return TenantRegistry(yaml_path="config/tenants.yaml")

    @pytest.mark.anyio
    async def test_missing_header_returns_400(self, registry: TenantRegistry) -> None:
        """D-01: Missing X-AnonReq-Tenant-ID returns HTTP 400."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/v1/test")
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "missing_tenant"
        assert "X-AnonReq-Tenant-ID header required" in body["message"]

    @pytest.mark.anyio
    async def test_unknown_tenant_returns_400(self, registry: TenantRegistry) -> None:
        """Unknown tenant_id returns HTTP 400."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/test", headers={"X-AnonReq-Tenant-ID": "nonexistent"}
            )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "invalid_tenant"
        assert "nonexistent" in body["message"]

    @pytest.mark.anyio
    async def test_disabled_tenant_returns_403(self, registry: TenantRegistry) -> None:
        """D-04: Disabled tenant returns HTTP 403."""
        from anonreq.tenant.models import TenantProfile

        registry.register(
            TenantProfile(
                tenant_id="disabled-tenant",
                display_name="Disabled",
                enabled=False,
            )
        )
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/test", headers={"X-AnonReq-Tenant-ID": "disabled-tenant"}
            )
        assert response.status_code == 403
        assert response.json()["error"] == "tenant_disabled"

    @pytest.mark.anyio
    async def test_valid_tenant_sets_request_state(
        self, registry: TenantRegistry
    ) -> None:
        """D-03: Valid tenant sets request.state.tenant_id and returns 200."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/test", headers={"X-AnonReq-Tenant-ID": "default"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == "default"

    @pytest.mark.anyio
    async def test_health_path_bypasses_tenant_validation(
        self, registry: TenantRegistry
    ) -> None:
        """Health path bypasses tenant validation (no header required)."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.anyio
    async def test_metrics_path_bypasses_tenant_validation(
        self, registry: TenantRegistry
    ) -> None:
        """Metrics path bypasses tenant validation (no header required)."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/metrics")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_tenant_profile_available_on_request_state(
        self, registry: TenantRegistry
    ) -> None:
        """TenantProfile is available on request.state.tenant_profile."""
        app = make_app(registry)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/test", headers={"X-AnonReq-Tenant-ID": "default"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_profile"] is not None
        assert body["tenant_profile"]["tenant_id"] == "default"
