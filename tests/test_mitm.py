"""Tests for the MITM middleware and handler."""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.proxy.ca_manager import CAManager
from anonreq.proxy.mitm_handler import MITMHandler, mitm_middleware
from anonreq.proxy.tls import TLSInterceptor


def _make_scope(
    method: str = "CONNECT",
    path: str = "api.openai.com:443",
    client_cert: bytes | None = None,
) -> dict:
    """Build a minimal ASGI scope dict for testing."""
    scope: dict = {
        "type": "http",
        "method": method,
        "path": path,
        "path_params": {},
        "query_string": b"",
        "headers": [],
        "scheme": "http",
    }
    if client_cert is not None:
        scope["client_certificate"] = client_cert
    return scope


@pytest.fixture
def ca_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture
def mock_tls():
    """Create a mock TLSInterceptor."""
    mock = MagicMock(spec=TLSInterceptor)
    mock.certificate_pinning_detected = MagicMock(return_value=False)
    return mock


@pytest.fixture
def mock_ca_manager(ca_dir):
    """Create a real CAManager for testing."""
    return CAManager(ca_dir=ca_dir, debounce=10.0)


@pytest.fixture
def handler(mock_tls, mock_ca_manager):
    """Create an MITMHandler with mocked dependencies."""
    return MITMHandler(tls_interceptor=mock_tls, ca_manager=mock_ca_manager)


class TestMITMHandler:
    """Tests for the MITMHandler class."""

    async def test_handle_connect_missing_target_returns_400(self, handler):
        """CONNECT with no target returns 400."""
        from starlette.requests import Request

        scope = _make_scope(path="")
        request = Request(scope)
        response = await handler.handle_connect(request)
        assert response.status_code == 400

    async def test_handle_connect_pinned_returns_426(self, handler):
        """CONNECT with pinned cert returns 426 with block header."""
        handler._tls.certificate_pinning_detected = MagicMock(return_value=True)
        from starlette.requests import Request

        scope = _make_scope(client_cert=b"fake-cert-der")
        request = Request(scope)
        response = await handler.handle_connect(request)
        assert response.status_code == 426
        assert response.headers.get("X-AnonReq-Blocked") == "certificate-pinning"

    async def test_handle_connect_unpinned_returns_200(self, handler):
        """CONNECT without pinning returns 200."""
        handler._tls.certificate_pinning_detected = MagicMock(return_value=False)
        from starlette.requests import Request

        scope = _make_scope()
        request = Request(scope)
        response = await handler.handle_connect(request)
        assert response.status_code == 200
        assert "X-AnonReq-Tunnel" in response.headers

    async def test_active_tunnel_count(self, handler):
        """active_tunnel_count is sensible."""
        assert handler.active_tunnel_count == 0

    async def test_close_clears_tunnels(self, handler):
        """close() clears active tunnels."""
        await handler.close()
        assert handler.active_tunnel_count == 0


class TestMITMMiddleware:
    """Tests for the mitm_middleware integration."""

    async def test_middleware_imports(self):
        """MITMHandler and mitm_middleware import successfully."""
        from anonreq.proxy.mitm_handler import MITMHandler, mitm_middleware
        assert MITMHandler is not None
        assert mitm_middleware is not None

    async def test_normal_request_passes_through(self, mock_tls, mock_ca_manager):
        """Non-CONNECT requests pass through to the normal pipeline."""
        app = FastAPI()
        handler = MITMHandler(tls_interceptor=mock_tls, ca_manager=mock_ca_manager)
        app.state.mitm_handler = handler

        @app.middleware("http")
        async def test_mitm(request, call_next):
            return await mitm_middleware(request, call_next)

        @app.get("/test")
        async def test_route():
            return {"status": "ok"}

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test")
            assert response.status_code == 200
