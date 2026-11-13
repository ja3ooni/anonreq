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
