"""create_app() governance auth: admin key, chat key, and tenant binding."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Request, Response
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.main import create_app


def _app() -> tuple[Any, AsyncMock]:
    app = create_app()
    slo = AsyncMock()
    slo.get_all_compliance.return_value = {}
    app.state.slo_engine = slo
    return app, slo


def _admin(tenant: str | None = "default") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}
    if tenant is not None:
        headers["X-AnonReq-Tenant-ID"] = tenant
    return headers


@pytest.mark.asyncio
async def test_admin_key_is_bound_to_server_tenant() -> None:
    assert settings.ADMIN_TENANT_ID == "default"
    app, slo = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.get("/v1/governance/status", headers=_admin())
        assert allowed.status_code == 200
        assert allowed.json()["tenant_id"] == "default"

        # Query naming another tenant: 403.
        cross = await client.get(
            "/v1/governance/status?tenant_id=other-tenant", headers=_admin(),
        )
        assert cross.status_code == 403
    assert all(call.args[0] == "default" for call in slo.get_all_compliance.await_args_list)


@pytest.mark.asyncio
async def test_admin_key_header_naming_another_tenant_is_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The key is bound to tenant-b; a valid header for "default" is refused."""
    app, slo = _app()
    monkeypatch.setattr(settings, "ADMIN_TENANT_ID", "tenant-b")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/governance/status", headers=_admin("default"))
    assert resp.status_code == 403
    slo.get_all_compliance.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_key_is_403_and_no_key_is_401() -> None:
    app, _slo = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        chat = await client.get(
            "/v1/governance/status",
            headers={
                "Authorization": f"Bearer {settings.API_KEY}",
                "X-AnonReq-Tenant-ID": "default",
            },
        )
        assert chat.status_code == 403

        missing = await client.get(
            "/v1/governance/status", headers={"X-AnonReq-Tenant-ID": "default"},
        )
        assert missing.status_code == 401

        wrong = await client.get(
            "/v1/governance/status",
            headers={
                "Authorization": "Bearer not-a-key",
                "X-AnonReq-Tenant-ID": "default",
            },
        )
        assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_preset_principal_without_key_is_401() -> None:
    """A principal already on request.state never skips key verification."""
    app, slo = _app()

    @app.middleware("http")
    async def _inject(
        request: Request, call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.role_principal = {
            "principal_id": "forged", "role": "administrator", "tenant_id": "default",
        }
        return await call_next(request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/governance/status", headers={"X-AnonReq-Tenant-ID": "default"},
        )
    assert resp.status_code == 401
    slo.get_all_compliance.assert_not_awaited()


def test_startup_fails_when_admin_key_has_no_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_TENANT_ID", None)
    with pytest.raises(RuntimeError, match="ANONREQ_ADMIN_TENANT_ID"):
        create_app()
    monkeypatch.setattr(settings, "ADMIN_TENANT_ID", "*")
    with pytest.raises(RuntimeError, match="ANONREQ_ADMIN_TENANT_ID"):
        create_app()


def test_startup_ok_without_admin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)
    monkeypatch.setattr(settings, "ADMIN_TENANT_ID", None)
    create_app()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/governance/audit/events", "/v1/governance/audit/verify"])
async def test_audit_routes_admin_chat_and_no_key(path: str) -> None:
    from types import SimpleNamespace

    app, _slo = _app()
    chain = AsyncMock()
    chain.get_events.return_value = []
    chain.verify_chain.return_value = SimpleNamespace(
        is_intact=True, checked_count=0, broken_at=None,
    )
    app.state.audit_chain = chain
    tenant = {"X-AnonReq-Tenant-ID": "default"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await client.get(path, headers=_admin())
        assert admin.status_code == 200
        chat = await client.get(
            path, headers={"Authorization": f"Bearer {settings.API_KEY}", **tenant},
        )
        assert chat.status_code == 403
        none = await client.get(path, headers=tenant)
        assert none.status_code == 401
    called = chain.get_events if path.endswith("events") else chain.verify_chain
    assert called.await_count == 1
    assert called.await_args.kwargs["tenant_id"] == "default"


@pytest.mark.asyncio
async def test_admin_key_refused_when_oidc_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """With OIDC configured, only verified tokens work; the admin key is 401."""
    from anonreq.auth.oidc import OIDCVerificationError

    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "anonreq")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/jwks")
    app, slo = _app()
    verifier = AsyncMock()
    verifier.verify_authorization.side_effect = OIDCVerificationError(
        "kid abc123 not in https://issuer.example/jwks",
    )
    app.state.oidc_verifier = verifier
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/governance/status", headers=_admin())
    assert resp.status_code == 401
    assert "abc123" not in resp.text
    assert "issuer.example" not in resp.text
    slo.get_all_compliance.assert_not_awaited()
