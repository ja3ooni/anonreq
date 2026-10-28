"""Anonymize-by-default regression: German PII never reaches the provider.

No classification rule matches this request, so the default action applies.
Before the fix the default was PASS, which skipped detection, and tool-call
arguments were detected but forwarded unmasked.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.provider import ProviderStage
from anonreq.routing.chat import build_pre_provider_pipeline

PROVIDER = "http://mock-provider.example"
GERMAN = (
    "Hans Müller, geb. 12.03.1980, Hauptstraße 12, 60311 Frankfurt, "
    "+49 170 1234567, hans.mueller@example.de"
)
VALUES = [
    "Hans Müller",
    "Müller",
    "12.03.1980",
    "Hauptstraße 12",
    "60311",
    "Frankfurt",
    "+49 170 1234567",
    "170 1234567",
    "hans.mueller@example.de",
]

# Presidio stand-in: what a German spaCy model returns for names/places.
_NER_SPANS = [
    ("Hans Müller", "PERSON"),
    ("Hauptstraße 12", "LOCATION"),
    ("Frankfurt", "LOCATION"),
    ("12.03.1980", "DATE_TIME"),
]


class _GermanNer:
    async def analyze_text_nodes(self, nodes: list[dict[str, Any]], **_kw: Any) -> list[Any]:
        results = []
        for node in nodes:
            value = node["value"]
            spans = []
            for text, entity in _NER_SPANS:
                start = value.find(text)
                if start >= 0:
                    spans.append(
                        {
                            "entity_type": entity,
                            "start": start,
                            "end": start + len(text),
                            "score": 0.85,
                            "source": "ner",
                        }
                    )
            results.append(spans)
        return results


class _Cache:
    async def store_mapping(self, *_a: Any, **_k: Any) -> bool:
        return True


def _request() -> dict[str, Any]:
    args = json.dumps({"kunde": GERMAN}, ensure_ascii=False)
    return {
        "model": "gpt-4o",
        "stream": False,
        "messages": [
            {"role": "user", "content": GERMAN},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "crm", "arguments": args}}
                ],
            },
        ],
    }


@pytest.mark.asyncio
@respx.mock
async def test_german_pii_never_reaches_provider_by_default() -> None:
    route = respx.post(f"{PROVIDER}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "ok"},
                     "finish_reason": "stop"}
                ],
            },
        )
    )
    pipeline = build_pre_provider_pipeline(_Cache(), _GermanNer())
    pipeline.register(ProviderStage(openai_base_url=PROVIDER, api_key="k", timeout=5.0))
    ctx = ProcessingContext(
        request_id="de-default",
        tenant_id="default",
        context_id="de-default",
        original_request=_request(),
        locale_header="de-DE",
    )
    ctx = await pipeline.run(ctx)

    assert not ctx.errors, ctx.errors
    assert ctx.classification_result is not None
    assert ctx.classification_result["action"] == "ANONYMIZE"
    assert route.called
    sent = route.calls.last.request.content.decode("utf-8")
    body = json.loads(sent)
    forwarded_args = body["messages"][1]["tool_calls"][0]["function"]["arguments"]
    for value in VALUES:
        assert value not in body["messages"][0]["content"], value
        assert value not in forwarded_args, value
        assert value not in sent, value
        assert json.dumps(value)[1:-1] not in sent, value
