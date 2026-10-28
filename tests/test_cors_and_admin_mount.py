"""CORS is off unless configured, and the RBAC admin router is mounted."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.cors import apply_cors, parse_cors_origins


def test_parse_cors_origins_splits_and_drops_blanks() -> None:
    assert parse_cors_origins(None) == []
    assert parse_cors_origins("") == []
    assert parse_cors_origins(" http://localhost:3000, ,https://demo.example ") == [
        "http://localhost:3000",
        "https://demo.example",
    ]


def test_apply_cors_is_a_noop_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CORS_ORIGINS", "")
    app = FastAPI()
    apply_cors(app)
    assert app.user_middleware == []


@pytest.mark.asyncio
async def test_apply_cors_allows_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:3000")
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    apply_cors(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/ping",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rbac_admin_and_debug_routes_are_mounted() -> None:
    from anonreq.main import app

    paths = app.openapi()["paths"]
    assert "/v1/admin/policies" in paths
    assert "/v1/admin/providers" in paths
    assert "/v1/admin/anonymization-events" in paths
    assert "/v1/admin/anonymization-events/export" in paths
    assert "/v1/debug/anonymize-preview" in paths
