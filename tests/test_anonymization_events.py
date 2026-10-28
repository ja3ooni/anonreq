"""Paginated anonymization events and unbounded CSV export."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import ASGITransport, AsyncClient

from anonreq.api.v1.admin.anonymization_events import router as events_router
from anonreq.config import settings
from anonreq.exceptions import global_exception_handler, http_exception_handler
from anonreq.models.audit import AuditEvent
from anonreq.services.audit_chain import AuditChainService
from anonreq.services.audit_export import ANONYMIZATION_EXPORT_PAGE_SIZE

ADMIN_KEY = "adminkey12345678901234567890"
RAW_VALUE = "secret-iban-DE89370400440532013000"


def _event(index: int, entity_type: str = "EMAIL_ADDRESS", row_id: int | None = None) -> AuditEvent:
    return AuditEvent(
        event_id=f"e{index}",
        prev_hash=None,
        hash="h",
        timestamp=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=index),
        tenant_id="acme",
        request_id=f"req-{index}",
        policy_id=None,
        decision="ANONYMIZE",
        provider="gpt-4o",
        latency_ms=3,
        event_type="anonymization",
        operator_id=None,
        change_type=None,
        prev_value_hash=None,
        new_value_hash=None,
        metadata_json=json.dumps({
            "entity_types": [entity_type, "IBAN_DE"],
            "entity_counts": {entity_type: 1, "IBAN_DE": 2},
            "token_count": 3,
            "locale": "de-DE",
            "model": "gpt-4o",
            "raw_value": RAW_VALUE,
        }),
        row_id=index + 1 if row_id is None else row_id,
    )


@pytest.fixture
def events_app():
    app = FastAPI()
    app.state.audit_chain = AsyncMock(spec=AuditChainService)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    @app.middleware("http")
    async def inject_role(request, call_next):
        request.state.tenant_id = request.headers.get("X-AnonReq-Tenant-ID", "acme")
        role = request.headers.get("X-Test-Role")
        if role:
            request.state.role_principal = {
                "principal_id": "test_admin",
                "role": role,
                "tenant_id": "*",
            }
        return await call_next(request)

    app.include_router(events_router)
    return app


def _headers(**extra: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    headers.update(extra)
    return headers


@pytest.mark.asyncio
async def test_events_require_admin(events_app: FastAPI) -> None:
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/v1/admin/anonymization-events")
        rejected = await client.get(
            "/v1/admin/anonymization-events",
            headers={"Authorization": "Bearer wrong-key"},
        )
        # The gateway chat key is a valid credential but not an admin.
        # (An injected lower role no longer overrides a verified admin key.)
        forbidden = await client.get(
            "/v1/admin/anonymization-events",
            headers={"Authorization": f"Bearer {settings.API_KEY}"},
        )
    assert missing.status_code == 401
    assert rejected.status_code == 401
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_events_page_filters_and_shape(events_app: FastAPI) -> None:
    events_app.state.audit_chain.get_events.return_value = [_event(2), _event(1)]
    events_app.state.audit_chain.count_events.return_value = 2
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/anonymization-events",
            headers=_headers(),
            params={
                "date_from": "2026-08-01T00:00:00Z",
                "date_to": "2026-08-31T00:00:00Z",
                "entity_type": "EMAIL_ADDRESS",
                "tenant_id": "acme",
                "sort": "timestamp:asc",
                "limit": 2,
                "cursor": "2026-08-01T00:00:00Z|4",
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 2
    assert body["next_cursor"] == "2026-08-01T00:00:01Z|2"
    assert "offset" not in body
    assert response.headers["cache-control"] == "no-store"
    assert len(body["items"]) == 2
    item = body["items"][0]
    assert item["request_id"] == "req-2"
    assert item["timestamp"] == "2026-08-01T00:00:02Z"
    assert item["tenant_id"] == "acme"
    assert item["model"] == "gpt-4o"
    assert item["locale"] == "de-DE"
    assert item["decision"] == "ANONYMIZE"
    assert item["token_count"] == 3
    assert item["entity_types"] == [
        {"type": "EMAIL_ADDRESS", "count": 1},
        {"type": "IBAN_DE", "count": 2},
    ]
    assert RAW_VALUE not in response.text

    kwargs = events_app.state.audit_chain.get_events.await_args.kwargs
    assert kwargs["event_type"] == "anonymization"
    assert kwargs["entity_type"] == "EMAIL_ADDRESS"
    assert kwargs["tenant_id"] == "acme"
    assert kwargs["sort"] == "timestamp:asc"
    assert kwargs["limit"] == 2
    assert kwargs["offset"] == 0
    assert kwargs["cursor_id"] == 4
    assert kwargs["date_from"] is not None
    assert kwargs["date_to"] is not None
    count_kwargs = events_app.state.audit_chain.count_events.await_args.kwargs
    assert count_kwargs["entity_type"] == "EMAIL_ADDRESS"
    assert count_kwargs["tenant_id"] == "acme"


@pytest.mark.asyncio
async def test_events_default_sort_and_limit_bounds(events_app: FastAPI) -> None:
    events_app.state.audit_chain.get_events.return_value = []
    events_app.state.audit_chain.count_events.return_value = 0
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get("/v1/admin/anonymization-events", headers=_headers())
        too_many = await client.get(
            "/v1/admin/anonymization-events",
            headers=_headers(),
            params={"limit": 201},
        )
    assert ok.status_code == 200
    assert ok.json() == {"total": 0, "limit": 50, "next_cursor": None, "items": []}
    assert events_app.state.audit_chain.get_events.await_args.kwargs["sort"] == "timestamp:desc"
    assert too_many.status_code == 422


@pytest.mark.asyncio
async def test_events_csv_streams_past_10k(events_app: FastAPI) -> None:
    total = 10001
    calls: list[dict] = []

    async def get_events(**kwargs):
        calls.append(kwargs)
        cursor_id = int(kwargs.get("cursor_id") or 0)
        limit = kwargs["limit"]
        start = cursor_id
        if start >= total:
            return []
        return [_event(index) for index in range(start, min(start + limit, total))]

    events_app.state.audit_chain.get_events.side_effect = get_events
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/anonymization-events/export",
            headers=_headers(),
            params={"entity_type": "EMAIL_ADDRESS", "tenant_id": "acme", "sort": "timestamp:asc"},
        )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert RAW_VALUE not in response.text
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == total
    assert list(rows[0]) == [
        "request_id",
        "timestamp",
        "tenant_id",
        "model",
        "locale",
        "decision",
        "token_count",
        "entity_types",
    ]
    assert rows[0]["request_id"] == "req-0"
    assert rows[-1]["request_id"] == "req-10000"
    assert json.loads(rows[0]["entity_types"]) == [
        {"type": "EMAIL_ADDRESS", "count": 1},
        {"type": "IBAN_DE", "count": 2},
    ]
    assert calls
    assert all(call["limit"] == ANONYMIZATION_EXPORT_PAGE_SIZE for call in calls)
    assert any(int(call.get("cursor_id") or 0) >= 10000 for call in calls)
    assert all(call["entity_type"] == "EMAIL_ADDRESS" for call in calls)
    assert all(call["sort"] == "timestamp:asc" for call in calls)
    assert all(call["limit"] != 10000 for call in calls)
    assert all(call["tenant_id"] == "acme" for call in calls)


@pytest.mark.asyncio
async def test_events_reject_foreign_tenant(events_app: FastAPI) -> None:
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/anonymization-events",
            headers=_headers(),
            params={"tenant_id": "other"},
        )
    assert response.status_code == 403
    events_app.state.audit_chain.get_events.assert_not_called()


@pytest.mark.asyncio
async def test_events_csv_escapes_formulas_and_appends_error_trailer(
    events_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dangerous = _event(0)
    dangerous.request_id = "=cmd|' /C calc'!A0"

    async def explode(*_args: object, **_kwargs: object):
        yield dangerous
        raise RuntimeError("database password leaked")

    monkeypatch.setattr(
        "anonreq.api.v1.admin.anonymization_events.iter_filtered_events",
        explode,
    )
    transport = ASGITransport(app=events_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/anonymization-events/export",
            headers=_headers(),
        )
    assert response.status_code == 200
    assert "database password leaked" not in response.text
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["request_id"].startswith("'=")
    assert rows[-1]["request_id"] == "#error"
    assert rows[-1]["decision"] == "export_failed"
    assert response.headers["cache-control"] == "no-store"



@pytest.fixture(autouse=True)
def _admin_key_bound_to_acme(monkeypatch: pytest.MonkeyPatch) -> None:
    """The admin key is bound on the server to the tenant these tests use."""
    import anonreq.admin.auth as admin_auth

    # Patch the settings object auth reads, even if another test swapped it.
    monkeypatch.setattr(admin_auth.settings, "ADMIN_TENANT_ID", "acme")
