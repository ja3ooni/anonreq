"""Unit tests for administrative config change history API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
            timestamp=datetime.now(UTC),
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
        response = await client.get("/v1/admin/audit/config-history?tenant_id=test_tenant", headers=headers)  # noqa: E501
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
            timestamp=datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC),
            tenant_id="test_tenant", request_id=None, policy_id=None, decision=None,
            provider=None, latency_ms=None, event_type="config_change",
            operator_id="op1", change_type="update", prev_value_hash="prev_h",
            new_value_hash="new_h", metadata_json=None
        )
    ]

    async def mock_get_events(_tenant_id=None, limit=100, offset=0, **_kwargs):
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
        assert "attachment; filename=config-history-export.jsonl" in response.headers["Content-Disposition"]  # noqa: E501

        content = response.text
        lines = [json.loads(line) for line in content.strip().split("\n") if line]
        assert len(lines) == 1
        assert lines[0]["event_id"] == "e1"
        assert lines[0]["prev_value_hash"] == "prev_h"
        assert lines[0]["new_value_hash"] == "new_h"
        assert lines[0]["operator_id"] == "op1"


@pytest.mark.asyncio
async def test_anonymization_export_json_omits_raw_values(audit_app):
    raw_iban = "DE89370400440532013000"
    audit_app.state.audit_chain.get_events.return_value = [
        AuditEvent(
            event_id="e2",
            prev_hash=None,
            hash="h2",
            timestamp=datetime(2026, 8, 14, 9, 0, 0, tzinfo=UTC),
            tenant_id="test_tenant",
            request_id="req-de-1",
            policy_id=None,
            decision="ANONYMIZE",
            provider="gpt-4o",
            latency_ms=12,
            event_type="anonymization",
            operator_id="dpo1",
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json=json.dumps({
                "entity_types": ["TAX_ID_DE", "IBAN_DE"],
                "entity_counts": {"TAX_ID_DE": 1, "IBAN_DE": 1},
                "token_count": 2,
                "locale": "de-DE",
                "model": "gpt-4o",
                "compliance_preset": "germany",
                "raw_iban": raw_iban,
            }),
        )
    ]

    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer testkey",
            "X-AnonReq-Role": "administrator",
            "X-AnonReq-Tenant-ID": "test_tenant",
        }
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=json",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.text
        assert raw_iban not in body
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["request_id"] == "req-de-1"
        assert "TAX_ID_DE" in rows[0]["entity_types"]
        assert "IBAN_DE" in rows[0]["entity_types"]
        assert "raw_iban" not in rows[0]

        csv_response = await client.get(
            "/v1/admin/audit/anonymization-export?format=csv",
            headers=headers,
        )
        assert csv_response.status_code == 200
        assert "text/csv" in csv_response.headers["content-type"]
        assert raw_iban not in csv_response.text
        assert "entity_types" in csv_response.text
