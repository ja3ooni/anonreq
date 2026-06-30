"""Tests for the HTTPBearer authentication and RequestContext system.

Tests verify:
- Valid Bearer token returns 200
- Missing, wrong, or malformed auth returns 401 with OpenAI envelope
- RequestContext populated with request_id, tenant_id
- Auth errors include request_id in response body
"""

from unittest.mock import ANY

import pytest
from fastapi import FastAPI, HTTPException, Depends, Request
from httpx import ASGITransport, AsyncClient
from uuid import uuid4

import structlog


@pytest.fixture
def auth_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Create a test app with auth, exception handlers, and request_id middleware.

    The app mimics the production setup from main.py (01-03) plus the
    auth dependency that will be wired in Task 2 of this plan.
    """
    # Ensure env var is set for settings singleton
    monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
    monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")

    # Force reload of settings — conftest.py setdefault may have already
    # instantiated the singleton with a different key. We reimport to
    # pick up our monkeypatched value.
    import importlib
    from anonreq import config
    importlib.reload(config)

    from anonreq.dependencies import auth_context
    from anonreq.exceptions import (
        global_exception_handler,
        http_exception_handler,
    )
    from anonreq.models.request_context import RequestContext

    app = FastAPI()

    # Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Middleware: set request_id before auth runs (per RESEARCH Open Q4)
    @app.middleware("http")
    async def set_request_id(request: Request, call_next):
        request_id = f"req_{uuid4().hex[:24]}"
        request.state.request_id = request_id
        request.state.context = RequestContext(request_id=request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        structlog.contextvars.unbind_contextvars("request_id")
        return response

    @app.get("/health")
    async def protected(ctx=Depends(auth_context)):
        return {
            "status": "ok",
            "request_id": ctx.request_id,
            "tenant_id": ctx.tenant_id,
        }

    return app


@pytest.fixture
async def client(auth_app: FastAPI) -> AsyncClient:
    """Yield an async HTTP client bound to the auth test app."""
    transport = ASGITransport(app=auth_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Valid auth ──────────────────────────────────────────────────────────


class TestValidAuth:
    """Tests for successful authentication scenarios."""

    async def test_valid_bearer_token_returns_200(self, client: AsyncClient):
        """Test 1: Request with valid Bearer token returns 200."""
        response = await client.get(
            "/health",
            headers={"Authorization": f"Bearer {'a' * 32}"},
        )
        assert response.status_code == 200

    async def test_valid_token_returns_openai_envelope(self, client: AsyncClient):
        """Valid auth response has OpenAI-compatible structure (error not present)."""
        response = await client.get(
            "/health",
            headers={"Authorization": f"Bearer {'a' * 32}"},
        )
        body = response.json()
        # Successful responses should NOT have an error envelope
        assert "error" not in body
        assert body["status"] == "ok"


# ── Missing auth ────────────────────────────────────────────────────────


class TestMissingAuth:
    """Tests for requests without Authorization header."""

    async def test_missing_auth_returns_401(self, client: AsyncClient):
        """Test 2: Request without Authorization header returns 401."""
        response = await client.get("/health")
        assert response.status_code == 401

    async def test_missing_auth_has_openai_envelope(self, client: AsyncClient):
        """Test 2: 401 response has OpenAI-compatible error envelope."""
        response = await client.get("/health")
        body = response.json()
        assert "error" in body
        assert "message" in body["error"]
        assert "type" in body["error"]
        assert "code" in body["error"]

    async def test_missing_auth_has_request_id(self, client: AsyncClient):
        """Test 7: Auth errors have request_id in response body."""
        response = await client.get("/health")
        body = response.json()
        assert "request_id" in body["error"]
        assert body["error"]["request_id"] is not None

    async def test_missing_auth_not_fastapi_default(self, client: AsyncClient):
        """Test 2: 401 does NOT use FastAPI's default {'detail': ...} format."""
        response = await client.get("/health")
        body = response.json()
        # FastAPI default returns {"detail": "Not authenticated"}
        # We check that the response is our envelope format
        assert "error" in body
        assert "detail" not in body


# ── Wrong token ─────────────────────────────────────────────────────────


class TestWrongToken:
    """Tests for requests with an incorrect Bearer token."""

    async def test_wrong_token_returns_401(self, client: AsyncClient):
        """Test 3: Request with wrong Bearer token returns 401."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-key-shorter-than-32"},
        )
        assert response.status_code == 401

    async def test_wrong_token_has_authentication_error_type(self, client: AsyncClient):
        """Test 3+5: Wrong token returns authentication_error type."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-key-shorter-than-32"},
        )
        body = response.json()
        assert body["error"]["type"] == "authentication_error"
        assert body["error"]["code"] == "invalid_api_key"

    async def test_wrong_token_has_request_id(self, client: AsyncClient):
        """Test 7: Wrong token error has request_id in response."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-key-shorter-than-32"},
        )
        body = response.json()
        assert "request_id" in body["error"]
        assert body["error"]["request_id"] is not None

    async def test_wrong_token_has_openai_envelope(self, client: AsyncClient):
        """Test 5: 401 response follows OpenAI envelope format."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-key-shorter-than-32"},
        )
        body = response.json()
        assert "error" in body
        assert "message" in body["error"]
        assert isinstance(body["error"]["message"], str)
        assert "request_id" in body["error"]


# ── Malformed auth (wrong scheme) ───────────────────────────────────────


class TestMalformedAuth:
    """Tests for requests with a malformed Authorization header."""

    async def test_basic_auth_scheme_returns_401(self, client: AsyncClient):
        """Test 4: Non-Bearer Authorization scheme returns 401."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    async def test_basic_auth_has_openai_envelope(self, client: AsyncClient):
        """Test 4: Non-Bearer scheme returns OpenAI envelope."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        body = response.json()
        assert "error" in body
        assert "request_id" in body["error"]

    async def test_malformed_auth_header_returns_401(self, client: AsyncClient):
        """Malformed auth header (e.g., 'Bearer') with no token returns 401."""
        response = await client.get(
            "/health",
            headers={"Authorization": "Bearer"},
        )
        assert response.status_code == 401


# ── RequestContext ──────────────────────────────────────────────────────


class TestRequestContext:
    """Tests for RequestContext population during authenticated requests."""

    async def test_request_context_has_request_id(self, client: AsyncClient):
        """Test 5: RequestContext has request_id starting with 'req_'."""
        response = await client.get(
            "/health",
            headers={"Authorization": f"Bearer {'a' * 32}"},
        )
        body = response.json()
        assert body["request_id"].startswith("req_")
        # request_id should be 4 (req_) + 24 hex chars = 28 chars
        assert len(body["request_id"]) == 28

    async def test_request_context_tenant_id_default(self, client: AsyncClient):
        """Test 6: RequestContext.tenant_id defaults to 'default'."""
        response = await client.get(
            "/health",
            headers={"Authorization": f"Bearer {'a' * 32}"},
        )
        body = response.json()
        assert body["tenant_id"] == "default"
