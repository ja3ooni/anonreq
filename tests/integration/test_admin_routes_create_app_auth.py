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
        # Only the admin key gets a default tenant; others need the header.
        chat = await client.get(path, headers={"Authorization": f"Bearer {settings.API_KEY}"})
        none = await client.get(path)
        chat_hdr = await client.get(
            path, headers={"Authorization": f"Bearer {settings.API_KEY}", **_TENANT},
        )
        monkeypatch.setattr(admin_auth.settings, "ADMIN_TENANT_ID", "tenant-b")
        # Header present but not the admin key's tenant: still 403.
        mismatch = await client.get(path, headers={**admin, **_TENANT})
    assert ok.status_code == 200, ok.text
    assert chat.status_code == 400
    assert chat.json()["error"] == "missing_tenant"
    assert none.status_code == 400
    assert none.json()["error"] == "missing_tenant"
    assert chat_hdr.status_code == 403
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


def test_single_tenant_with_several_tenants_fails_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    import anonreq.config as config

    tenants = tmp_path / "tenants.yaml"
    tenants.write_text(
        "tenants:\n"
        "  - tenant_id: default\n    enabled: true\n"
        "  - tenant_id: acme\n    enabled: true\n",
    )
    monkeypatch.setattr(config.settings, "TENANTS_CONFIG_PATH", str(tenants))
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", True)
    with pytest.raises(RuntimeError, match="2 tenants are configured"):
        create_app()
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", False)
    create_app()


def test_single_tenant_with_one_tenant_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    import anonreq.config as config

    tenants = tmp_path / "tenants.yaml"
    tenants.write_text("tenants:\n  - tenant_id: default\n    enabled: true\n")
    monkeypatch.setenv("ANONREQ_TENANTS_CONFIG_PATH", str(tenants))
    monkeypatch.setattr(config.settings, "TENANTS_CONFIG_PATH", str(tenants))
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", True)
    app = create_app()
    assert [p.tenant_id for p in app.state.tenant_registry.list_all()] == ["default"]


@pytest.mark.asyncio
async def test_single_tenant_no_admin_default_when_oidc_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OIDC on: the admin key gets no default tenant, so no header is 400."""
    from starlette.requests import Request

    import anonreq.config as config
    from anonreq.middleware.tenant import _single_tenant_default

    monkeypatch.setattr(config.settings, "SINGLE_TENANT", True)
    scope = {
        "type": "http", "method": "GET", "path": "/v1/x", "query_string": b"",
        "headers": [(b"authorization", f"Bearer {settings.ADMIN_API_KEY}".encode())],
    }
    assert _single_tenant_default(Request(scope)) == settings.ADMIN_TENANT_ID
    monkeypatch.setattr(config.settings, "OIDC_ISSUER", "https://issuer.test")
    monkeypatch.setattr(config.settings, "OIDC_AUDIENCE", "anonreq")
    monkeypatch.setattr(config.settings, "OIDC_JWKS_URL", "https://issuer.test/jwks")
    assert _single_tenant_default(Request(scope)) == ""

    app = _app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            _AUDIT_ROUTES[0], headers={"Authorization": f"Bearer {settings.ADMIN_API_KEY}"},
        )
    assert response.status_code == 400
    assert response.json()["error"] == "missing_tenant"


_BAD_TENANT_HEADERS = {
    "non_ascii": "défault".encode(),
    "non_ascii_latin1": "d\xe9fault".encode("latin-1"),
    "control_char": b"def\x01ault",
    "del_char": b"def\x7fault",
    "over_long": b"t" * 65,
}
_CHAT = "/v1/chat/completions"


async def _bad_header_call(client: AsyncClient, path: str, key: str, value: bytes) -> Any:
    headers = [
        (b"authorization", f"Bearer {key}".encode()),
        (b"x-anonreq-tenant-id", value),
    ]
    if path == _CHAT:
        return await client.post(
            path, headers=headers,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        )
    return await client.get(path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("single_tenant", [False, True])
@pytest.mark.parametrize("path", [_CHAT, *_AUDIT_ROUTES])
@pytest.mark.parametrize("case", sorted(_BAD_TENANT_HEADERS))
async def test_malformed_tenant_header_is_400_invalid_tenant(
    monkeypatch: pytest.MonkeyPatch, path: str, case: str, single_tenant: bool,
) -> None:
    import anonreq.config as config

    app = _app(monkeypatch)
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", single_tenant)
    key = settings.API_KEY if path == _CHAT else settings.ADMIN_API_KEY
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _bad_header_call(client, path, key or "", _BAD_TENANT_HEADERS[case])
    assert response.status_code == 400, response.text
    assert response.json() == {
        "error": "invalid_tenant",
        "message": "Invalid X-AnonReq-Tenant-ID header",
    }
    app.state.audit_chain.get_events.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [_CHAT, *_AUDIT_ROUTES])
async def test_non_ascii_authorization_does_not_crash(
    monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    """Single-tenant default compares the key; non-ASCII must not be a 500."""
    import anonreq.config as config

    app = _app(monkeypatch)
    monkeypatch.setattr(config.settings, "SINGLE_TENANT", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            path, headers=[(b"authorization", "Bearer clé".encode())],
        )
    assert response.status_code == 400
    assert response.json()["error"] == "missing_tenant"


@pytest.mark.parametrize("case", sorted(_BAD_TENANT_HEADERS))
def test_admin_auth_rejects_malformed_header_outside_middleware(case: str) -> None:
    """Admin auth itself maps a malformed header to InvalidTenantHeaderError."""
    from starlette.requests import Request

    scope = {
        "type": "http", "method": "GET", "path": "/x", "query_string": b"",
        "headers": [(b"x-anonreq-tenant-id", _BAD_TENANT_HEADERS[case])],
    }
    with pytest.raises(admin_auth.InvalidTenantHeaderError):
        admin_auth._reject_header_mismatch(Request(scope), "default")
