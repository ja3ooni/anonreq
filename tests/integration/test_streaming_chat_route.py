"""Route-level regression coverage for stream:true chat completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ANONREQ_API_KEY", "a" * 32)
os.environ.setdefault("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANONREQ_PRESIDIO_URL", "http://localhost:5001")

from anonreq.config import settings
from anonreq.models.chat import ChatRequest
from anonreq.models.request_context import RequestContext
from anonreq.providers.adapter import ProviderCapabilities, ProviderRequest
from anonreq.routing.chat import _stream_chat_completions, router as chat_router
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent


SESSION_ID = "stream_test_session"


class StableUUID:
    hex = SESSION_ID


@dataclass
class FakeAlias:
    provider: str = "openai"
    model: str = "gpt-4o-mini"


class FakeAliasRegistry:
    def __init__(self) -> None:
        self.resolved: list[str] = []

    def resolve(self, alias: str) -> FakeAlias:
        self.resolved.append(alias)
        return FakeAlias()


class FakeProviderRegistry:
    def __init__(self, adapter: FakeStreamingAdapter) -> None:
        self.adapter = adapter
        self.providers: list[str] = []

    def get_adapter(self, provider: str) -> "FakeStreamingAdapter":
        self.providers.append(provider)
        return self.adapter


class FakePreProviderPipeline:
    async def run(self, proc_ctx: Any) -> Any:
        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.transformed_request = {
            "model": proc_ctx.original_request["model"],
            "messages": [{"role": "user", "content": "Hello [EMAIL_0]"}],
            "stream": True,
        }
        proc_ctx.detections = [{"entity_type": "EMAIL", "start": 6, "end": 15, "score": 1.0}]
        return proc_ctx


class InMemoryCache:
    def __init__(self) -> None:
        self.mappings: dict[tuple[str, str], dict[str, str]] = {}

    async def store_mapping(self, tenant_id: str, session_id: str, mapping: dict[str, str]) -> None:
        self.mappings[(tenant_id, session_id)] = dict(mapping)

    async def get_mapping(self, tenant_id: str, session_id: str) -> dict[str, str]:
        return dict(self.mappings.get((tenant_id, session_id), {}))

    async def delete_mapping(self, tenant_id: str, session_id: str) -> None:
        self.mappings.pop((tenant_id, session_id), None)


class FakeStreamingAdapter:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.capabilities = ProviderCapabilities(streaming=True)
        self.translated_contexts: list[Any] = []
        self.stream_requests: list[ProviderRequest] = []
        self.events_started = 0
        self.events_completed = 0

    @property
    def provider_name(self) -> str:
        return "openai"

    def translate_request(self, ctx: Any) -> ProviderRequest:
        self.translated_contexts.append(ctx)
        return ProviderRequest(body=dict(ctx.original_request or {}))

    async def stream_events(self, request: ProviderRequest) -> AsyncIterator[StreamEvent]:
        self.stream_requests.append(request)
        for event in self._events():
            self.events_started += 1
            yield event
            self.events_completed += 1
            if self.mode == "raise_after_first" and self.events_started == 1:
                raise RuntimeError("https://provider.example/v1 leaked user@example.com ANONREQ_OPENAI_API_KEY")

    def _events(self) -> list[StreamEvent]:
        if self.mode == "error_event":
            return [
                StreamEvent(event_type=EventType.TEXT_DELTA, provider="openai", delta_text="Safe "),
                StreamEvent(
                    event_type=EventType.ERROR,
                    provider="openai",
                    metadata={
                        "message": "https://provider.example/v1 user@example.com ANONREQ_OPENAI_API_KEY",
                        "type": "upstream_error",
                    },
                ),
            ]
        return [
            StreamEvent(event_type=EventType.TEXT_DELTA, provider="openai", delta_text="Hello "),
            StreamEvent(event_type=EventType.TEXT_DELTA, provider="openai", delta_text="[EMA"),
            StreamEvent(event_type=EventType.TEXT_DELTA, provider="openai", delta_text="IL_0]"),
            StreamEvent(event_type=EventType.FINISH, provider="openai", finish_reason=FinishReason.STOP),
        ]


async def _make_cache() -> InMemoryCache:
    return InMemoryCache()


def _install_streaming_state(app: FastAPI, cache: InMemoryCache, adapter: FakeStreamingAdapter) -> None:
    app.state.cache_manager = cache
    app.state.presidio_client = AsyncMock()
    app.state.alias_registry = FakeAliasRegistry()
    app.state.provider_registry = FakeProviderRegistry(adapter)
    app.state.locale_negotiator = object()
    app.state.recognizer_merger = object()
    app.state.checksum_registry = object()
    app.state.active_compliance_presets = []


@pytest.fixture
async def streaming_app(monkeypatch: pytest.MonkeyPatch):
    cache = await _make_cache()
    adapter = FakeStreamingAdapter()
    app = FastAPI()
    _install_streaming_state(app, cache, adapter)
    app.include_router(chat_router)
    monkeypatch.setattr("anonreq.routing.chat.uuid4", lambda: StableUUID())
    monkeypatch.setattr("anonreq.routing.chat.build_pre_provider_pipeline", lambda *args, **kwargs: FakePreProviderPipeline())
    monkeypatch.setattr(
        "anonreq.pipeline.provider.ProviderStage.execute",
        AsyncMock(side_effect=AssertionError("legacy ProviderStage POST path reached")),
    )
    monkeypatch.setattr(
        "anonreq.pipeline.provider.ProviderStage.execute",
        AsyncMock(side_effect=AssertionError("legacy ProviderStage POST path reached")),
    )
    await cache.store_mapping("default", SESSION_ID, {"[EMAIL_0]": "user@example.com"})
    yield app, cache, adapter


@pytest.mark.asyncio
async def test_stream_true_returns_sse_restores_split_tokens_and_cleans_up(streaming_app):
    app, cache, adapter = streaming_app
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fast",
                "messages": [{"role": "user", "content": "Hello user@example.com"}],
                "stream": True,
            },
            headers={"Authorization": f"Bearer {settings.API_KEY}"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["connection"] == "keep-alive"

    body = response.text
    assert '"choices":[{"delta":{"content":"Hello user@example.com"}' in body
    assert "[EMA" not in body
    assert "[EMAIL_0]" not in body
    assert body.endswith("data: [DONE]\n\n")

    assert app.state.alias_registry.resolved == ["fast"]
    assert app.state.provider_registry.providers == ["openai"]
    assert len(adapter.translated_contexts) == 1
    assert len(adapter.stream_requests) == 1
    assert adapter.translated_contexts[0].provider == "openai"
    assert adapter.translated_contexts[0].model == "gpt-4o-mini"
    assert adapter.translated_contexts[0].original_request["model"] == "gpt-4o-mini"
    assert adapter.translated_contexts[0].original_request["stream"] is True
    assert await cache.get_mapping("default", SESSION_ID) == {}


@pytest.mark.asyncio
async def test_provider_error_event_emits_generic_error_and_cleans_up(monkeypatch: pytest.MonkeyPatch):
    cache = await _make_cache()
    adapter = FakeStreamingAdapter(mode="error_event")
    app = FastAPI()
    _install_streaming_state(app, cache, adapter)
    app.include_router(chat_router)
    monkeypatch.setattr("anonreq.routing.chat.uuid4", lambda: StableUUID())
    monkeypatch.setattr("anonreq.routing.chat.build_pre_provider_pipeline", lambda *args, **kwargs: FakePreProviderPipeline())
    await cache.store_mapping("default", SESSION_ID, {"[EMAIL_0]": "user@example.com"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "fast", "messages": [{"role": "user", "content": "Hello user@example.com"}], "stream": True},
            headers={"Authorization": f"Bearer {settings.API_KEY}"},
        )

    assert response.status_code == 200
    assert '"error":{"message":"stream error","type":"provider_error"}' in response.text
    assert "provider.example" not in response.text
    assert "ANONREQ_OPENAI_API_KEY" not in response.text
    assert "user@example.com" not in response.text
    assert "Hello [EMAIL_0]" not in response.text
    assert await cache.get_mapping("default", SESSION_ID) == {}


@pytest.mark.asyncio
async def test_provider_exception_emits_generic_error_and_cleans_up(monkeypatch: pytest.MonkeyPatch):
    cache = await _make_cache()
    adapter = FakeStreamingAdapter(mode="raise_after_first")
    app = FastAPI()
    _install_streaming_state(app, cache, adapter)
    monkeypatch.setattr("anonreq.routing.chat.uuid4", lambda: StableUUID())
    monkeypatch.setattr("anonreq.routing.chat.build_pre_provider_pipeline", lambda *args, **kwargs: FakePreProviderPipeline())
    monkeypatch.setattr(
        "anonreq.pipeline.provider.ProviderStage.execute",
        AsyncMock(side_effect=AssertionError("legacy ProviderStage POST path reached")),
    )
    await cache.store_mapping("default", SESSION_ID, {"[EMAIL_0]": "user@example.com"})

    request = SimpleNamespace(
        app=app,
        state=SimpleNamespace(),
        headers={},
        is_disconnected=AsyncMock(return_value=False),
    )
    response = await _stream_chat_completions(
        ChatRequest(model="fast", messages=[{"role": "user", "content": "Hello user@example.com"}], stream=True),
        request,  # type: ignore[arg-type]
        RequestContext(request_id="req_stream_test", tenant_id="default"),
    )

    body = "".join([chunk async for chunk in response.body_iterator])
    assert '"error":{"message":"stream error","type":"provider_error"}' in body
    assert "provider.example" not in body
    assert "ANONREQ_OPENAI_API_KEY" not in body
    assert "user@example.com" not in body
    assert await cache.get_mapping("default", SESSION_ID) == {}


@pytest.mark.asyncio
async def test_client_disconnect_stops_provider_iteration_and_cleans_up(monkeypatch: pytest.MonkeyPatch):
    cache = await _make_cache()
    adapter = FakeStreamingAdapter()
    app = FastAPI()
    _install_streaming_state(app, cache, adapter)
    monkeypatch.setattr("anonreq.routing.chat.uuid4", lambda: StableUUID())
    monkeypatch.setattr("anonreq.routing.chat.build_pre_provider_pipeline", lambda *args, **kwargs: FakePreProviderPipeline())
    monkeypatch.setattr(
        "anonreq.pipeline.provider.ProviderStage.execute",
        AsyncMock(side_effect=AssertionError("legacy ProviderStage POST path reached")),
    )
    cleanup_states: list[str] = []

    class SpySessionCleanup:
        def __init__(self, cache_manager: Any, tenant_id: str, session_id: str, audit_logger: Any = None) -> None:
            self.cache_manager = cache_manager
            self.tenant_id = tenant_id
            self.session_id = session_id

        async def cleanup(self, terminal_state: str = "FINISH") -> None:
            cleanup_states.append(terminal_state)
            await self.cache_manager.delete_mapping(self.tenant_id, self.session_id)

    monkeypatch.setattr("anonreq.routing.chat.SessionCleanup", SpySessionCleanup)
    await cache.store_mapping("default", SESSION_ID, {"[EMAIL_0]": "user@example.com"})

    disconnect_checks = 0

    async def is_disconnected() -> bool:
        nonlocal disconnect_checks
        disconnect_checks += 1
        return disconnect_checks > 1

    request = SimpleNamespace(
        app=app,
        state=SimpleNamespace(),
        headers={},
        is_disconnected=is_disconnected,
    )
    response = await _stream_chat_completions(
        ChatRequest(model="fast", messages=[{"role": "user", "content": "Hello user@example.com"}], stream=True),
        request,  # type: ignore[arg-type]
        RequestContext(request_id="req_stream_test", tenant_id="default"),
    )

    body = "".join([chunk async for chunk in response.body_iterator])
    assert body == ""
    assert cleanup_states == ["CLIENT_DISCONNECT"]
    assert adapter.events_started == 2
    assert adapter.events_completed == 1
    assert await cache.get_mapping("default", SESSION_ID) == {}
