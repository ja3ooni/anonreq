"""Integration tests for Governance API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import ASGITransport, AsyncClient

from anonreq.exceptions import global_exception_handler, http_exception_handler
from anonreq.routes.governance import router as governance_router
from anonreq.services.audit_chain import AuditChainService
from anonreq.services.slo_engine import SLOCompliance, SLOEngine


@pytest.fixture
def gov_app():
    app = FastAPI()
    app.state.slo_engine = AsyncMock(spec=SLOEngine)
    app.state.audit_chain = AsyncMock(spec=AuditChainService)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    @app.middleware("http")
    async def inject_principal(request, call_next):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            request.state.role_principal = None
        else:
            role = request.headers.get("X-AnonReq-Role", "administrator")
            tenant_id = request.headers.get("X-AnonReq-Tenant-ID", "test_tenant")
            request.state.role_principal = {
                "principal_id": "test_admin",
                "role": role,
                "tenant_id": tenant_id,
            }
        return await call_next(request)

    app.include_router(governance_router)
    return app


@pytest.mark.asyncio
async def test_get_governance_status_authorized(gov_app):
    gov_app.state.slo_engine.get_all_compliance.return_value = {
        "success_rate": [
            SLOCompliance(
                slo_name="success_rate",
                target=99.9,
                current=100.0,
                compliant=True,
                window_type="daily",
                window_key="2026-07-03",
                last_breach=None,
            )
        ]
    }

    transport = ASGITransport(app=gov_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "administrator",
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/governance/status?tenant_id=test_tenant", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test_tenant"
        assert "success_rate" in data["slos"]
        assert data["slos"]["success_rate"][0]["compliant"] is True


@pytest.mark.asyncio
async def test_get_governance_status_unauthorized(gov_app):
    transport = ASGITransport(app=gov_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No Authorization header
        response = await client.get("/v1/governance/status")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_governance_status_insufficient_role(gov_app):
    transport = ASGITransport(app=gov_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "operator",  # Operators cannot read status
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/governance/status", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_governance_breaches(gov_app):
    from anonreq.models.audit import AuditEvent
    from datetime import datetime, timezone

    gov_app.state.audit_chain.get_events.return_value = [
        AuditEvent(
            event_id="e1",
            prev_hash=None,
            hash="h1",
            timestamp=datetime.now(timezone.utc),
            tenant_id="test_tenant",
            request_id=None,
            policy_id=None,
            decision=None,
            provider=None,
            latency_ms=None,
            event_type="slo_breach_detected",
            operator_id=None,
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json='{"slo_name": "success_rate"}',
            retention_days=2557,
        )
    ]

    transport = ASGITransport(app=gov_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "administrator",
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/governance/breaches?tenant_id=test_tenant", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["event_id"] == "e1"
        assert data["data"][0]["details"]["slo_name"] == "success_rate"
