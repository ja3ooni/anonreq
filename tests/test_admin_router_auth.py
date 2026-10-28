"""Every route on the RBAC admin router requires an admin credential."""

from __future__ import annotations

import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from anonreq.admin.router import admin_router, require_auth

_PARAM = re.compile(r"\{[^}]+\}")


def _walk(router: object, prefix: str = "") -> list[tuple[str, set[str]]]:
    found: list[tuple[str, set[str]]] = []
    for route in getattr(router, "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if isinstance(route, APIRoute) and path and methods:
            found.append((prefix + path, set(methods)))
            continue
        original = getattr(route, "original_router", None)
        if original is None:
            continue
        context = getattr(route, "include_context", None)
        child_prefix = prefix + (getattr(context, "prefix", "") or "")
        found.extend(_walk(original, child_prefix))
    return found


@pytest.mark.asyncio
async def test_admin_router_routes_reject_anonymous_callers() -> None:
    app = FastAPI()
    app.include_router(admin_router, dependencies=[Depends(require_auth)])
    routes = _walk(admin_router)
    assert routes, "admin router exposed no routes"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path, methods in routes:
            concrete = _PARAM.sub("sample", path)
            for method in sorted(methods - {"HEAD", "OPTIONS"}):
                response = await client.request(method, concrete, json={})
                assert response.status_code in {401, 403}, (
                    f"{method} {concrete} returned {response.status_code}"
                )
