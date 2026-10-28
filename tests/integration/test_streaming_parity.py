"""stream:true runs the same governance as non-streaming requests.

- The pre-provider pipeline is built with app_state, so PDP/PEP, inbound
  DLP and tool governance run.
- Outbound DLP inspects streamed provider text before release and fails
  closed on a block or an inspection error.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.pipeline.dlp import InboundDLPStage
from anonreq.pipeline.stages import PolicyEnforcementStage
from anonreq.pipeline.tool_governance import ToolGovernanceStage
from anonreq.routing.chat import build_pre_provider_pipeline
from anonreq.routing.chat import router as chat_router
from anonreq.state import get_app_state
from tests.integration.test_streaming_chat_route import (
    SESSION_ID,
    FakePreProviderPipeline,
    FakeStreamingAdapter,
    StableUUID,
    _install_streaming_state,
    _make_cache,
)

_BODY = {
    "model": "fast",
    "messages": [{"role": "user", "content": "Hello user@example.com"}],
    "stream": True,
}


async def _app(monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]) -> tuple[FastAPI, Any]:
    cache = await _make_cache()
    adapter = FakeStreamingAdapter()
    app = FastAPI()
    _install_streaming_state(app, cache, adapter)
    app.include_router(chat_router)
    monkeypatch.setattr("anonreq.routing.chat.uuid4", lambda: StableUUID())

    def _build(*_args: Any, **kwargs: Any) -> FakePreProviderPipeline:
        captured.update(kwargs)
        return FakePreProviderPipeline()

    monkeypatch.setattr("anonreq.routing.chat.build_pre_provider_pipeline", _build)
    await cache.store_mapping("default", SESSION_ID, {"[EMAIL_0]": "user@example.com"})
    return app, cache


async def _post(app: FastAPI) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json=_BODY,
            headers={"Authorization": f"Bearer {settings.API_KEY}"},
        )
    assert response.status_code == 200
    return response.text


@pytest.mark.asyncio
async def test_streaming_pipeline_is_built_with_app_state(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    app, _ = await _app(monkeypatch, captured)
    await _post(app)
    assert captured.get("app_state") is not None
    assert captured["app_state"] is get_app_state(app) or captured["app_state"] == get_app_state(
        app
    )


def test_pre_provider_stages_receive_app_state() -> None:
    state = SimpleNamespace()
    manager = build_pre_provider_pipeline(AsyncMock(), AsyncMock(), app_state=state)
    governed = [
        stage
        for stage in manager.stages
        if isinstance(stage, (PolicyEnforcementStage, InboundDLPStage, ToolGovernanceStage))
    ]
    assert len(governed) == 3
    for stage in governed:
        assert stage._app_state is state


@pytest.mark.asyncio
async def test_outbound_dlp_block_stops_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    app, cache = await _app(monkeypatch, {})
    engine = SimpleNamespace(inspect=AsyncMock(return_value=SimpleNamespace(is_blocked=True)))
    get_app_state(app).dlp_engine = engine
    text = await _post(app)
    assert "outbound_dlp" in text
    assert "user@example.com" not in text
    assert "Hello" not in text
    assert engine.inspect.await_count >= 1
    # The inspected text is the tokenized provider output, not restored PII.
    inspected = engine.inspect.await_args.args[0]
    assert "user@example.com" not in inspected
    assert await cache.get_mapping("default", SESSION_ID) == {}


@pytest.mark.asyncio
async def test_outbound_dlp_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = await _app(monkeypatch, {})
    engine = SimpleNamespace(inspect=AsyncMock(side_effect=RuntimeError("down")))
    get_app_state(app).dlp_engine = engine
    text = await _post(app)
    assert "outbound_dlp" in text
    assert "user@example.com" not in text
    assert "down" not in text


@pytest.mark.asyncio
async def test_outbound_dlp_allow_streams_restored_text(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = await _app(monkeypatch, {})
    get_app_state(app).dlp_engine = SimpleNamespace(
        inspect=AsyncMock(return_value=SimpleNamespace(is_blocked=False))
    )
    text = await _post(app)
    assert "Hello user@example.com" in text
    assert text.endswith("data: [DONE]\n\n")


class _SubstringEngine:
    """Blocks when the inspected text contains the full secret."""

    def __init__(self, secret: str) -> None:
        self.secret = secret

    async def inspect(self, text: str, _tenant: str) -> Any:
        return SimpleNamespace(is_blocked=self.secret in text)


@pytest.mark.asyncio
async def test_secret_split_across_chunks_emits_no_fragment() -> None:
    from anonreq.exceptions import OutboundDLPError
    from anonreq.routing.chat import _StreamingOutboundDLP

    secret = "sk_live_ABCDEF1234567890"
    dlp = _StreamingOutboundDLP(SimpleNamespace(dlp_engine=_SubstringEngine(secret)), "t")
    released: list[str] = []
    released += await dlp.feed("x" * 600)
    released += await dlp.feed("key is " + secret[:10])
    with pytest.raises(OutboundDLPError):
        released += await dlp.feed(secret[10:] + " done")
    joined = "".join(released)
    assert secret[:4] not in joined
    assert "key is" not in joined


@pytest.mark.asyncio
async def test_text_held_until_hold_length_passed() -> None:
    from anonreq.routing.chat import _StreamingOutboundDLP

    dlp = _StreamingOutboundDLP(SimpleNamespace(dlp_engine=_SubstringEngine("nope")), "t")
    assert await dlp.feed("a" * 10) == []
    assert await dlp.feed("b" * 600) == ["a" * 10]
    assert await dlp.flush("c") == ["b" * 600, "c"]
