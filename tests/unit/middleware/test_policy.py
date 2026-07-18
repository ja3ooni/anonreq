"""Unit tests for PolicyMiddleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.middleware.policy import PolicyMiddleware
from anonreq.policy.models import PolicyAction, PolicyDecision
from anonreq.policy.pep import PolicyEnforcementResult


def _make_app(
    pdp_result: Any | None = None,
    pep_result: Any | None = None,
    pdp_side_effect: Exception | None = None,
    pep_side_effect: Exception | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.pdp = AsyncMock()
    app.state.pep = AsyncMock()

    if pdp_side_effect:
        app.state.pdp.evaluate_all.side_effect = pdp_side_effect
    elif pdp_result:
        app.state.pdp.evaluate_all.return_value = pdp_result

    if pep_side_effect:
        app.state.pep.enforce.side_effect = pep_side_effect
    elif pep_result:
        app.state.pep.enforce.return_value = pep_result

    app.add_middleware(PolicyMiddleware)

    @app.get("/v1/chat/completions")
    async def chat() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.mark.unit
class TestPolicyMiddleware:
    @pytest.mark.anyio
    async def test_skip_health_path(self) -> None:
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/health")
        assert r.status_code == 200

    @pytest.mark.anyio
    async def test_pdp_exception_returns_503(self) -> None:
        app = _make_app(pdp_side_effect=RuntimeError("PDP down"))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 503
        assert r.headers.get("x-anonreq-blocked") == "true"

    @pytest.mark.anyio
    async def test_pep_exception_returns_503(self) -> None:
        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            reason="ok",
            matched_rules=[],
        )
        app = _make_app(
            pdp_result=decision,
            pep_side_effect=RuntimeError("PEP down"),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 503

    @pytest.mark.anyio
    async def test_pep_blocks_request(self) -> None:
        decision = PolicyDecision(
            action=PolicyAction.BLOCK,
            reason="blocked",
            matched_rules=[],
        )
        pep_result = PolicyEnforcementResult(
            action=PolicyAction.BLOCK,
            should_forward=False,
            status_code=403,
            body={"detail": "forbidden"},
            headers={},
        )
        app = _make_app(pdp_result=decision, pep_result=pep_result)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 403

    @pytest.mark.anyio
    async def test_allowed_request_forwards(self) -> None:
        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            reason="ok",
            matched_rules=[],
        )
        pep_result = PolicyEnforcementResult(
            action=PolicyAction.ALLOW,
            should_forward=True,
            status_code=200,
            body={},
            headers={"X-Custom": "val"},
        )
        app = _make_app(pdp_result=decision, pep_result=pep_result)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 200
        assert r.headers.get("x-custom") == "val"

    @pytest.mark.anyio
    async def test_missing_pdp_pep_passes_through(self) -> None:
        app = FastAPI()
        app.state = type("S", (), {})()  # no pdp/pep
        app.add_middleware(PolicyMiddleware)

        @app.get("/v1/test")
        async def test_route() -> dict[str, str]:
            return {"ok": "true"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/test")
        assert r.status_code == 200
