"""Unit tests for administrative config change history API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import ASGITransport, AsyncClient

from anonreq.api.v1.admin.audit import router as admin_audit_router
from anonreq.exceptions import global_exception_handler, http_exception_handler
from anonreq.models.audit import AuditEvent
from anonreq.services.audit_chain import AuditChainService


@pytest.fixture
def audit_app():
    app = FastAPI()
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

    app.include_router(admin_audit_router)
    return app


@pytest.mark.asyncio
async def test_get_config_history_authorized(audit_app):
    audit_app.state.audit_chain.get_events.return_value = [
        AuditEvent(
            event_id="e1", prev_hash=None, hash="h1",
            timestamp=datetime.now(timezone.utc),
            tenant_id="test_tenant", request_id=None, policy_id=None, decision=None,
            provider=None, latency_ms=None, event_type="config_change",
            operator_id="op1", change_type="update", prev_value_hash=None,
            new_value_hash=None, metadata_json=None
        )
    ]
    audit_app.state.audit_chain.count_events.return_value = 1

    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "administrator",
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/admin/audit/config-history?tenant_id=test_tenant", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["event_id"] == "e1"
        assert data["items"][0]["operator_id"] == "op1"


@pytest.mark.asyncio
async def test_get_config_history_unauthorized(audit_app):
    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/admin/audit/config-history")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_config_history_insufficient_role(audit_app):
    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "operator",  # Operator has insufficient permission
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/admin/audit/config-history", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_config_history_streaming(audit_app):
    events = [
        AuditEvent(
            event_id="e1", prev_hash=None, hash="h1",
            timestamp=datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc),
            tenant_id="test_tenant", request_id=None, policy_id=None, decision=None,
            provider=None, latency_ms=None, event_type="config_change",
            operator_id="op1", change_type="update", prev_value_hash="prev_h",
            new_value_hash="new_h", metadata_json=None
        )
    ]

    async def mock_get_events(tenant_id=None, limit=100, offset=0, **kwargs):
        if offset >= len(events):
            return []
        return events[offset : offset + limit]

    audit_app.state.audit_chain.get_events.side_effect = mock_get_events

    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "administrator",
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get("/v1/admin/audit/config-history/export", headers=headers)
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/x-ndjson"
        assert "attachment; filename=config-history-export.jsonl" in response.headers["Content-Disposition"]

        content = response.text
        lines = [json.loads(line) for line in content.strip().split("\n") if line]
        assert len(lines) == 1
        assert lines[0]["event_id"] == "e1"
        assert lines[0]["prev_value_hash"] == "prev_h"
        assert lines[0]["new_value_hash"] == "new_h"
        assert lines[0]["operator_id"] == "op1"
