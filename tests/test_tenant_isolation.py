"""Tenant isolation tests for critical-findings Finding 3.

- Request with no ``request.state.tenant_id`` → 503 with
  ``X-AnonReq-Blocked: true`` (fail-secure, never 200, never
  default-evaluated).
- With ``ANONREQ_SINGLE_TENANT=true`` → explicit single-tenant fallback
  to ``"default"`` still works (conscious deployment choice).
- Two tenants with divergent policies → decisions differ per tenant
  (tenant id is threaded into ``ProcessingContext``, no cross-tenant
  leakage at the middleware layer).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from anonreq.middleware.policy import PolicyMiddleware


class _FakeDecision:
    pass


class _FakeEnforcement:
    should_forward = True
    status_code = 200
    body = None
    headers: dict[str, str] = {}


class _FakePEP:
    """PEP double that always passes enforcement through."""

    async def enforce(self, decision, ctx):
        return _FakeEnforcement()


class _CapturePDP:
    """PDP double that captures the tenant it was asked to evaluate."""

    def __init__(self, seen: list[str]) -> None:
        self._seen = seen

    async def evaluate_all(self, ctx):
        self._seen.append(ctx.tenant_id)
        return _FakeDecision()


class _DivergentPDP:
    """PDP double returning a per-tenant decision marker."""

    async def evaluate_all(self, ctx):
        return SimpleNamespace(tenant=ctx.tenant_id)


class _DivergentPEP:
    """PEP double blocking one tenant and passing the other."""

    async def enforce(self, decision, ctx):
        if decision.tenant == "tenant-a":
            return SimpleNamespace(
                should_forward=False,
                status_code=403,
                body={"reason": "blocked for tenant-a"},
                headers={},
            )
        return SimpleNamespace(
            should_forward=True, status_code=200, body=None, headers={}
        )


def _make_request(
    tenant_id: str | None, app_state: SimpleNamespace, path: str = "/v1/chat/completions"
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "app": SimpleNamespace(state=app_state),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    request.state.request_id = "test_req_001"
    if tenant_id is not None:
        request.state.tenant_id = tenant_id
    return request


async def _ok_call_next(request: Request) -> Response:
    return JSONResponse(status_code=200, content={"ok": True})


def _middleware(seen: list[str]) -> tuple[PolicyMiddleware, SimpleNamespace]:
    state = SimpleNamespace(pdp=_CapturePDP(seen), pep=_FakePEP())
    mw = PolicyMiddleware.__new__(PolicyMiddleware)
    return mw, state


class TestMissingTenantFailsSecure:
    @pytest.mark.asyncio
    async def test_missing_tenant_returns_503_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """No tenant context → 503 + X-AnonReq-Blocked, PDP never runs."""
        monkeypatch.delenv("ANONREQ_SINGLE_TENANT", raising=False)
        seen: list[str] = []
        mw, state = _middleware(seen)
        request = _make_request(None, state)

        response = await mw.dispatch(request, _ok_call_next)

        assert response.status_code == 503
        assert response.headers.get("X-AnonReq-Blocked") == "true"
        assert seen == [], "PDP must not evaluate when tenant context is missing"

    def test_extract_tenant_id_returns_none_when_missing(self):
        """_extract_tenant_id returns None (never silent 'default')."""
        scope = {"type": "http", "method": "GET", "path": "/"}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)
        assert PolicyMiddleware._extract_tenant_id(request) is None

    def test_extract_tenant_id_returns_set_tenant(self):
        """_extract_tenant_id passes through a valid tenant."""
        scope = {"type": "http", "method": "GET", "path": "/"}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)
        request.state.tenant_id = "acme"
        assert PolicyMiddleware._extract_tenant_id(request) == "acme"


class TestSingleTenantMode:
    @pytest.mark.asyncio
    async def test_single_tenant_mode_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """ANONREQ_SINGLE_TENANT=true → explicit fallback, request proceeds."""
        monkeypatch.setenv("ANONREQ_SINGLE_TENANT", "true")
        seen: list[str] = []
        mw, state = _middleware(seen)
        request = _make_request(None, state)

        response = await mw.dispatch(request, _ok_call_next)

        assert response.status_code == 200
        assert seen == ["default"]


class TestTenantDivergence:
    @pytest.mark.asyncio
    async def test_divergent_policies_per_tenant(self):
        """Same path, different tenants → different enforcement outcomes."""
        state = SimpleNamespace(pdp=_DivergentPDP(), pep=_DivergentPEP())
        mw = PolicyMiddleware.__new__(PolicyMiddleware)

        resp_a = await mw.dispatch(_make_request("tenant-a", state), _ok_call_next)
        resp_b = await mw.dispatch(_make_request("tenant-b", state), _ok_call_next)

        assert resp_a.status_code == 403
        assert resp_b.status_code == 200
