"""Tests for proxy-only passthrough mode."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.gateway.passthrough import (
    ProxyOnlyHandler,
    GatewayStatus,
    ProxyMode,
)


class TestProxyOnlyHandler:
    """Tests for proxy-only mode — no anonymization, policy evaluation only."""

    @pytest.fixture
    def handler(self):
        return ProxyOnlyHandler()

    async def test_passthrough_request(self, handler):
        response = await handler.passthrough(
            method="POST",
            path="/v1/chat/completions",
            headers={"content-type": "application/json"},
            body=b'{"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}',
        )
        assert response["status"] == "forwarded"
        assert response["mode"] == "proxy-only"

    async def test_passthrough_no_anonymization(self, handler):
        body = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "My email is john@example.com"}]}'
        response = await handler.passthrough(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body=body,
        )
        assert response["status"] == "forwarded"
        assert response["anonymization_applied"] is False
        assert response["body"] == body

    async def test_passthrough_p95_latency(self, handler):
        body = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}'
        latencies = []
        for _ in range(10):
            start = time.monotonic()
            await handler.passthrough(
                method="POST",
                path="/v1/chat/completions",
                headers={},
                body=body,
            )
            latencies.append((time.monotonic() - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 5.0, f"P95 latency {p95}ms exceeds 5ms"

    async def test_proxy_only_mode_setting(self, handler):
        assert handler.mode == ProxyMode.PROXY_ONLY

    async def test_passthrough_preserves_headers(self, handler):
        headers = {"authorization": "Bearer test123", "content-type": "application/json"}
        response = await handler.passthrough(
            method="POST",
            path="/v1/chat/completions",
            headers=headers,
            body=b"test",
        )
        assert response["headers"] is not None

    async def test_passthrough_get_request(self, handler):
        response = await handler.passthrough(
            method="GET",
            path="/v1/models",
            headers={},
            body=b"",
        )
        assert response["status"] == "forwarded"


class TestGatewayStatus:
    """Tests for the gateway status endpoint logic."""

    @pytest.fixture
    def status(self):
        return GatewayStatus()

    def test_default_status(self, status):
        info = status.get_status()
        assert info["service"] == "AnonReq Gateway"
        assert "mode" in info
        assert info["mode"] == "proxy-only"
        assert "uptime_seconds" in info
        assert "proxy_config" in info

    def test_status_includes_proxy_config(self, status):
        info = status.get_status()
        config = info.get("proxy_config", {})
        assert "block_all_unintercepted_ai" in config
        assert "allowed_providers" in config

    def test_status_allowed_providers(self, status):
        info = status.get_status()
        providers = info.get("proxy_config", {}).get("allowed_providers", [])
        assert len(providers) > 0
        assert "openai" in providers

    def test_status_uptime_increases(self, status):
        info1 = status.get_status()
        info2 = status.get_status()
        assert info2["uptime_seconds"] >= info1["uptime_seconds"]

    def test_set_mode(self, status):
        status.set_mode("full")
        assert status.get_status()["mode"] == "full"

    def test_set_mode_back_to_proxy_only(self, status):
        status.set_mode("full")
        status.set_mode("proxy-only")
        assert status.get_status()["mode"] == "proxy-only"


class TestProxyOnlyModeIntegration:
    """Integration tests for proxy-only mode with FastAPI."""

    async def test_gateway_status_endpoint(self):
        app = FastAPI()
        status = GatewayStatus()

        from fastapi import APIRouter

        router = APIRouter(prefix="/v1/gateway")

        @router.get("/status")
        async def get_status():
            return status.get_status()

        app.include_router(router)

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/gateway/status")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "AnonReq Gateway"
            assert "mode" in data
            assert "uptime_seconds" in data
            assert "proxy_config" in data

    async def test_passthrough_block_all_unintercepted_ai(self):
        handler = ProxyOnlyHandler(block_all_unintercepted_ai=True)
        assert handler.block_all_unintercepted_ai is True

    async def test_proxy_only_mode_no_detection(self):
        handler = ProxyOnlyHandler()
        body = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}]}'
        response = await handler.passthrough(
            method="POST",
            path="/v1/chat/completions",
            headers={"content-type": "application/json"},
            body=body,
        )
        assert not response.get("anonymization_applied", True), (
            "Proxy-only mode must not apply anonymization"
        )
