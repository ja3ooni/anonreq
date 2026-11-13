"""POST /v1/chat/completions with ``X-AnonReq-Locale: bg`` (what the web
playground sends) masks a Bulgarian EGN before the provider sees it and
restores it in the response. Real app, real route, real pipeline; only the
upstream provider (respx) and Presidio (empty NER stand-in) are mocked.
Synthetic, generator-built values only.
"""

# Bulgarian test text is Cyrillic on purpose.
# ruff: noqa: RUF001

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.locale.checksums.bulgaria import generate_egn
from anonreq.main import create_app
from anonreq.models.request_context import RequestContext
from anonreq.routing.chat import build_pipeline

EGN = generate_egn(dt.date(1985, 3, 15), serial=456)
PROMPT = f"Здравейте, моля проверете досието на клиент с ЕГН {EGN} и обобщете."


class _NoNer:
    """Presidio stand-in: no NER spans (there is no Bulgarian model)."""

    def __init__(self) -> None:
        self.languages: list[str] = []

    async def analyze_text_nodes(
        self, nodes: list[dict[str, Any]], language: str = "en", **_kw: Any
    ) -> list[Any]:
        self.languages.append(language)
        return [[] for _ in nodes]


class _Cache:
    def __init__(self) -> None:
        self.mappings: dict[tuple[str, str], dict[str, str]] = {}

    async def store_mapping(self, tenant_id: str, session_id: str, mapping: dict[str, str]) -> bool:
        self.mappings[(tenant_id, session_id)] = dict(mapping)
        return True

    async def get_mapping(self, tenant_id: str, session_id: str) -> dict[str, str]:
        return dict(self.mappings.get((tenant_id, session_id), {}))

    async def delete_mapping(self, tenant_id: str, session_id: str) -> bool:
        self.mappings.pop((tenant_id, session_id), None)
        return True


@pytest.fixture
def bg_app(monkeypatch: pytest.MonkeyPatch):
    # Operator opt-in: accept structured-ID-only masking for bg-BG.
    monkeypatch.setattr(settings, "BG_STRUCTURED_ONLY", True)
    return _make_app(monkeypatch)


@pytest.fixture
def bg_app_default(monkeypatch: pytest.MonkeyPatch):
    # Default deployment: ANONREQ_BG_STRUCTURED_ONLY unset.
    monkeypatch.setattr(settings, "BG_STRUCTURED_ONLY", False)
    return _make_app(monkeypatch)


def _make_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "PROVIDER_API_KEY", "sk-upstream-test-key-000000000000")
    app = create_app()
    app.dependency_overrides[auth_context] = lambda: RequestContext(
        request_id="bg-endpoint", tenant_id="default"
    )
    cache = _Cache()
    ner = _NoNer()
    app.state.cache_manager = cache
    app.state.presidio_client = ner
    app.state.pipeline = build_pipeline(cache, ner)  # type: ignore[arg-type]
    return app, cache, ner


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["bg", "bg-BG"])
async def test_bg_header_masks_egn_before_provider(bg_app, header: str) -> None:
    app, cache, ner = bg_app
    upstream = f"{settings.PROVIDER_BASE_URL.rstrip('/')}/v1/chat/completions"
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(upstream).mock(
            side_effect=lambda request: httpx.Response(
                200,
                json={
                    "id": "chatcmpl-bg",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "gpt-4o",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            # Echo the masked prompt so restore is exercised.
                            "content": "Получих: "
                            + json.loads(request.content)["messages"][0]["content"],
                        },
                        "finish_reason": "stop",
                    }],
                },
            )
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": PROMPT}]},
                headers={
                    "Authorization": f"Bearer {settings.API_KEY}",
                    "X-AnonReq-Tenant-ID": "default",
                    "X-AnonReq-Locale": header,
                },
            )

    assert response.status_code == 200, response.text
    assert route.call_count == 1
    sent = route.calls.last.request.content.decode("utf-8")
    forwarded = json.loads(sent)["messages"][0]["content"]
    assert EGN not in sent
    assert "[EGN_" in forwarded, forwarded
    assert forwarded.startswith("Здравейте, моля проверете досието на клиент с ЕГН [EGN_")
    assert forwarded.endswith("] и обобщете.")
    # bg is not a Presidio language here: analyzed with the English model.
    assert ner.languages == ["en"]

    content = response.json()["choices"][0]["message"]["content"]
    assert content == "Получих: " + PROMPT
    assert response.headers["X-AnonReq-Processed"] == "true"
    # No Bulgarian NER: names and addresses are not covered, and we say so.
    assert response.headers["X-AnonReq-NER-Coverage"] == "structured_only"
    assert cache.mappings == {}  # cleanup deleted the session mapping


@pytest.mark.asyncio
async def test_unknown_language_is_still_rejected(bg_app) -> None:
    app, _cache, _ner = bg_app
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(url__regex=r".*/v1/chat/completions").mock(
            return_value=httpx.Response(500)
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": PROMPT}]},
                headers={
                    "Authorization": f"Bearer {settings.API_KEY}",
                    "X-AnonReq-Tenant-ID": "default",
                    "X-AnonReq-Locale": "zz",
                },
            )
    assert response.status_code == 400, response.text
    assert "Locale negotiation failed" in response.text, response.text
    assert not route.called


def _headers(locale: str = "bg") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.API_KEY}",
        "X-AnonReq-Tenant-ID": "default",
        "X-AnonReq-Locale": locale,
    }


def _upstream() -> str:
    return f"{settings.PROVIDER_BASE_URL.rstrip('/')}/v1/chat/completions"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("header", ["bg", "bg-BG", "en, bg"])
async def test_bg_is_refused_with_422_by_default(bg_app_default, header: str, stream: bool) -> None:
    app, cache, _ner = bg_app_default
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(_upstream()).mock(return_value=httpx.Response(500))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "stream": stream,
                    "messages": [{"role": "user", "content": PROMPT}],
                },
                headers=_headers(header),
            )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "bg_ner_not_cleared"
    assert error["type"] == "locale_not_cleared"
    assert "ANONREQ_BG_STRUCTURED_ONLY" in error["message"]
    assert EGN not in response.text
    assert response.headers["X-AnonReq-NER-Coverage"] == "structured_only"
    assert not route.called
    assert cache.mappings == {}


@pytest.mark.asyncio
async def test_default_deployment_still_serves_other_locales(bg_app_default) -> None:
    app, _cache, _ner = bg_app_default
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(_upstream()).mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "created": 0, "model": "gpt-4o",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "ok"}}],
            })
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hallo"}]},
                headers=_headers("de-DE"),
            )
    assert response.status_code == 200, response.text
    assert route.called
    assert "X-AnonReq-NER-Coverage" not in response.headers


class _EchoStreamingAdapter:
    """Provider stand-in for the streaming route: echoes the masked prompt."""

    def __init__(self) -> None:
        from anonreq.providers.adapter import ProviderCapabilities

        self.capabilities = ProviderCapabilities(streaming=True)
        self.forwarded: list[str] = []

    def translate_request(self, ctx: Any) -> Any:
        from anonreq.providers.adapter import ProviderRequest

        return ProviderRequest(body=dict(ctx.original_request or {}))

    async def stream_events(self, request: Any) -> Any:
        from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent

        forwarded = request.body["messages"][0]["content"]
        self.forwarded.append(forwarded)
        for piece in ("Получих: ", forwarded[:7], forwarded[7:]):
            yield StreamEvent(event_type=EventType.TEXT_DELTA, provider="openai", delta_text=piece)
        yield StreamEvent(
            event_type=EventType.FINISH, provider="openai", finish_reason=FinishReason.STOP
        )


class _Alias:
    provider = "openai"
    model = "gpt-4o"


class _Aliases:
    def resolve(self, _alias: str) -> _Alias:
        return _Alias()


class _Providers:
    def __init__(self, adapter: _EchoStreamingAdapter) -> None:
        self.adapter = adapter

    def get_adapter(self, _provider: str) -> _EchoStreamingAdapter:
        return self.adapter


@pytest.mark.asyncio
async def test_streaming_bg_response_carries_ner_coverage_header(bg_app) -> None:
    app, _cache, _ner = bg_app
    adapter = _EchoStreamingAdapter()
    app.state.alias_registry = _Aliases()
    app.state.provider_registry = _Providers(adapter)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "stream": True,
                "messages": [{"role": "user", "content": PROMPT}],
            },
            headers=_headers("bg"),
        )
    assert response.status_code == 200, response.text
    assert response.headers["X-AnonReq-NER-Coverage"] == "structured_only"
    [forwarded] = adapter.forwarded
    assert EGN not in forwarded
    assert "[EGN_" in forwarded
    text = "".join(
        json.loads(line[6:])["choices"][0]["delta"].get("content") or ""
        for line in response.text.splitlines()
        if line.startswith("data: {") and json.loads(line[6:]).get("choices")
    )
    assert text == "Получих: " + PROMPT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream", "status"),
    [
        (httpx.ConnectError("provider unreachable"), 503),
        (httpx.ReadTimeout("upstream timeout"), 504),
    ],
)
async def test_post_forward_errors_carry_ner_coverage_header(bg_app, upstream, status: int) -> None:
    app, _cache, _ner = bg_app
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(_upstream())
        if isinstance(upstream, Exception):
            route.mock(side_effect=upstream)
        else:
            route.mock(return_value=upstream)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": PROMPT}]},
                headers=_headers("bg"),
            )
    assert route.called
    assert response.status_code == status, response.text
    assert response.headers["X-AnonReq-NER-Coverage"] == "structured_only"
    assert EGN not in response.text
