"""create_app(): admin audit, events and preview routes need a real credential."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

import anonreq.admin.auth as admin_auth
from anonreq.config import settings
from anonreq.main import create_app

_GET_ROUTES = (
    "/v1/admin/anonymization-events",
    "/v1/admin/anonymization-events/export",
    "/v1/admin/audit/config-history",
    "/v1/admin/audit/anonymization-export?format=json",
)
_PREVIEW = "/v1/debug/anonymize-preview"
_TENANT = {"X-AnonReq-Tenant-ID": "default"}


def _app(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "DEBUG_PREVIEW_ENABLED", True)
    app = create_app()
    chain = AsyncMock()
    chain.get_events.return_value = []
    chain.count_events.return_value = 0
    chain.max_row_id.return_value = None
    app.state.audit_chain = chain
    return app


async def _call(client: AsyncClient, path: str, headers: dict[str, str]) -> Any:
    if path == _PREVIEW:
        return await client.post(path, headers=headers, json={"prompt": "hi"})
    return await client.get(path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [*_GET_ROUTES, _PREVIEW])
async def test_no_credential_is_401(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _call(client, path, dict(_TENANT))
    assert response.status_code == 401
    app.state.audit_chain.get_events.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [*_GET_ROUTES, _PREVIEW])
async def test_preset_principal_without_key_is_401(
    monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    """A principal already on request.state never skips key verification."""
    app = _app(monkeypatch)

    @app.middleware("http")
    async def _forge(request: Any, call_next: Any) -> Any:
        request.state.role_principal = {
            "principal_id": "forged", "role": "administrator", "tenant_id": "default",
        }
        return await call_next(request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _call(client, path, dict(_TENANT))
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [*_GET_ROUTES, _PREVIEW])
async def test_chat_key_is_403_and_admin_key_header_mismatch_is_403(
    monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        chat = await _call(
            client, path, {"Authorization": f"Bearer {settings.API_KEY}", **_TENANT},
        )
        monkeypatch.setattr(admin_auth.settings, "ADMIN_TENANT_ID", "tenant-b")
        mismatch = await _call(
            client, path, {"Authorization": f"Bearer {settings.ADMIN_API_KEY}", **_TENANT},
        )
    assert chat.status_code == 403
    assert mismatch.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _GET_ROUTES)
async def test_admin_key_reads_server_tenant(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _call(
            client, path, {"Authorization": f"Bearer {settings.ADMIN_API_KEY}", **_TENANT},
        )
    assert response.status_code == 200, response.text
    for call in app.state.audit_chain.get_events.await_args_list:
        assert call.kwargs["tenant_id"] == "default"


def test_startup_fails_when_admin_key_equals_gateway_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", settings.API_KEY)
    with pytest.raises(RuntimeError, match="must differ"):
        create_app()
