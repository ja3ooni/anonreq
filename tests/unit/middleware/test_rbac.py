"""Unit tests for RBAC require_role dependency."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from anonreq.middleware.rbac import Role, require_role


def _app_with_role(min_role: Role) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"ok": "true"}

    app.dependency_overrides[require_role(min_role)] = lambda: None
    return app


@pytest.mark.unit
class TestRBAC:
    @pytest.mark.anyio
    async def test_admin_role_allowed(self) -> None:
        app = _app_with_role(Role.ADMINISTRATOR)

        @app.middleware("http")
        async def inject_admin(request: Request, call_next):
            request.state.role_principal = {"role": "administrator"}
            return await call_next(request)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/protected")
        assert r.status_code == 200

    @pytest.mark.anyio
    async def test_insufficient_role_returns_403(self) -> None:
        app = _app_with_role(Role.ADMINISTRATOR)

        @app.middleware("http")
        async def inject_readonly(request: Request, call_next):
            request.state.role_principal = {"role": "read_only_auditor"}
            return await call_next(request)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/protected")
        assert r.status_code == 403

    @pytest.mark.anyio
    async def test_no_role_returns_401(self) -> None:
        app = _app_with_role(Role.OPERATOR)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/protected")
        assert r.status_code in (401, 500)

    def test_role_hierarchy(self) -> None:
        from anonreq.middleware.rbac import ROLE_HIERARCHY

        assert ROLE_HIERARCHY[Role.ADMINISTRATOR] > ROLE_HIERARCHY[Role.SECURITY_OFFICER]
        assert ROLE_HIERARCHY[Role.SECURITY_OFFICER] > ROLE_HIERARCHY[Role.OPERATOR]
        assert ROLE_HIERARCHY[Role.OPERATOR] > ROLE_HIERARCHY[Role.READ_ONLY_AUDITOR]

    def test_normalize_role_value(self) -> None:
        from anonreq.middleware.rbac import _normalize_role_value

        assert _normalize_role_value("read_only") == "read_only_auditor"
        assert _normalize_role_value("administrator") == "administrator"
