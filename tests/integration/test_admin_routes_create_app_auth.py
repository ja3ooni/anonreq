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


_AUDIT_ROUTES = (
    "/v1/admin/audit/config-history",
    "/v1/admin/audit/anonymization-export?format=json",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _AUDIT_ROUTES)
async def test_admin_key_alone_works_without_gateway_key(
    monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    """Only the admin key is sent: no gateway key is needed on audit routes."""
    app = _app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await client.get(
            path, headers={"Authorization": f"Bearer {settings.ADMIN_API_KEY}", **_TENANT},
        )
        chat = await client.get(
            path, headers={"Authorization": f"Bearer {settings.API_KEY}", **_TENANT},
        )
        none = await client.get(path, headers=dict(_TENANT))
    assert admin.status_code == 200, admin.text
    assert chat.status_code == 403
    assert none.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _AUDIT_ROUTES)
async def test_single_tenant_defaults_missing_header(
    monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    import anonreq.config as config

    app = _app(monkeypatch)
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", True)
    admin = {"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.get(path, headers=admin)
        chat = await client.get(path, headers={"Authorization": f"Bearer {settings.API_KEY}"})
        none = await client.get(path)
        monkeypatch.setattr(admin_auth.settings, "ADMIN_TENANT_ID", "tenant-b")
        # Header present but not the admin key's tenant: still 403.
        mismatch = await client.get(path, headers={**admin, **_TENANT})
    assert ok.status_code == 200, ok.text
    assert chat.status_code == 403
    assert none.status_code == 401
    assert mismatch.status_code == 403
    for call in app.state.audit_chain.get_events.await_args_list:
        assert call.kwargs["tenant_id"] == "default"


@pytest.mark.asyncio
async def test_missing_header_is_400_without_single_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import anonreq.config as config

    app = _app(monkeypatch)
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/admin/audit/config-history",
            headers={"Authorization": f"Bearer {settings.ADMIN_API_KEY}"},
        )
    assert resp.status_code == 400
