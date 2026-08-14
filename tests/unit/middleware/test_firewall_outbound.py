"""Unit tests for OutboundFirewallMiddleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from anonreq.firewall.models import (
    DetectionCategory,
    DetectionResult,
    FirewallAction,
    SeverityLevel,
)
from anonreq.middleware.firewall_outbound import OutboundFirewallMiddleware


class FakeFirewallGate:
    """Minimal stub implementing the FirewallRuleEngine.evaluate API.

    OutboundFirewallMiddleware wraps ``engine`` in OutboundFirewallGate,
    which calls ``evaluate`` for both pre- and post-restore checks.
    """

    def __init__(self, block_pre: bool = False, block_post: bool = False) -> None:
        self._block_pre = block_pre
        self._block_post = block_post

    async def evaluate(self, _text: str) -> list[DetectionResult]:
        if self._block_pre or self._block_post:
            return [
                DetectionResult(
                    category=DetectionCategory.SECRET_EXFILTRATION,
                    confidence=0.99,
                    rule_id="test-block",
                    severity=SeverityLevel.HIGH,
                    action=FirewallAction.BLOCK,
                    matched_text_snippet="blocked",
                )
            ]
        return []


def _make_response_body(text: str) -> bytes:
    import json

    return json.dumps(
        {"choices": [{"message": {"content": text}}]}
    ).encode()


def _app(gate: FakeFirewallGate | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(OutboundFirewallMiddleware, engine=gate)

    @app.get("/v1/chat/completions")
    async def chat() -> StreamingResponse:
        body = _make_response_body("Hello world")
        return StreamingResponse(iter([body]), media_type="application/json")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.mark.unit
class TestOutboundFirewallMiddleware:
    @pytest.mark.anyio
    async def test_skip_health_path(self) -> None:
        app = _app(FakeFirewallGate(block_post=True))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/health")
        assert r.status_code == 200

    @pytest.mark.anyio
    async def test_no_gate_passes_through(self) -> None:
        app = _app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 200

    @pytest.mark.anyio
    async def test_clean_response_passes(self) -> None:
        app = _app(FakeFirewallGate(block_pre=False, block_post=False))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 200

    @pytest.mark.anyio
    async def test_post_restore_block_returns_451(self) -> None:
        app = _app(FakeFirewallGate(block_post=True))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/chat/completions")
        assert r.status_code == 451
        body = r.json()
        assert "error" in body
