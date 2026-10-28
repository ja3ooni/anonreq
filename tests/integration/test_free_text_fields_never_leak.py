"""Every free-text field of a chat request is masked before the provider.

The test walks a full OpenAI-style request, plants a unique e-mail address
in every free-text string leaf, runs the real pre-provider pipeline and the
ProviderStage against a mocked provider, then walks the forwarded body and
asserts that none of the planted values arrived.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from anonreq.models.chat import ChatRequest
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.provider import ProviderStage
from anonreq.routing.chat import build_pre_provider_pipeline

PROVIDER = "http://mock-provider.example"

# Structural fields: identifiers and enums, not free text.
_STRUCTURAL_KEYS = {"model", "role", "type", "id", "tool_call_id", "url", "tool_choice", "detail"}
_STRUCTURAL_PATHS = {("function", "name")}  # tool/function names are identifiers

_TEMPLATE: dict[str, Any] = {
    "model": "gpt-4o",
    "stream": False,
    "user": "FREE",
    "messages": [
        {"role": "system", "content": "FREE"},
        {"role": "user", "name": "FREE", "content": "FREE"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "FREE"},
                {"type": "image_url", "image_url": {"url": "https://img.example/x.png"}},
                {"type": "text", "text": "FREE"},
            ],
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "crm_create", "arguments": "FREE"}},
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "FREE"},
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "crm_create",
                "description": "FREE",
                "parameters": {
                    "type": "object",
                    "description": "FREE",
                    "properties": {
                        "kunde": {"type": "string", "description": "FREE"},
                        "adressen": {
                            "type": "array",
                            "items": {"type": "string", "description": "FREE"},
                        },
                    },
                },
            },
        }
    ],
}


def _string_leaves(node: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _string_leaves(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _string_leaves(value, (*path, index))
    elif isinstance(node, str):
        yield path, node


def _is_free_text(path: tuple[Any, ...]) -> bool:
    if not path or path[-1] in _STRUCTURAL_KEYS:
        return False
    return not (len(path) >= 2 and tuple(path[-2:]) in _STRUCTURAL_PATHS)


def _plant(template: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    body = copy.deepcopy(template)
    planted: list[str] = []
    for path, _ in list(_string_leaves(body)):
        if not _is_free_text(path):
            continue
        value = f"kunde{len(planted)}@beispiel.de"
        if path[-1] == "arguments":
            value_text = json.dumps({"email": value})
        else:
            value_text = f"Kontakt {value} bitte"
        target: Any = body
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value_text
        planted.append(value)
    return body, planted


class _NoNer:
    async def analyze_text_nodes(self, nodes: list[Any], **_kw: Any) -> list[Any]:
        return [[] for _ in nodes]


class _Cache:
    async def store_mapping(self, *_a: Any, **_k: Any) -> bool:
        return True


def test_template_covers_every_free_text_field_of_the_request_model() -> None:
    """Guard: the template exercises the free-text fields ChatRequest keeps."""
    planted_body, planted = _plant(_TEMPLATE)
    validated = ChatRequest.model_validate(planted_body).model_dump(exclude_none=True)
    kept = [v for _, v in _string_leaves(validated) if "@beispiel.de" in v]
    assert len(kept) == len(planted) == 12


@pytest.mark.asyncio
@respx.mock
async def test_planted_pii_in_any_free_text_field_never_reaches_provider() -> None:
    route = respx.post(f"{PROVIDER}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"id": "x", "object": "chat.completion", "created": 0, "model": "gpt-4o",
                  "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                               "finish_reason": "stop"}]},
        )
    )
    body, planted = _plant(_TEMPLATE)
    request = ChatRequest.model_validate(body).model_dump(exclude_none=True)

    pipeline = build_pre_provider_pipeline(_Cache(), _NoNer())
    pipeline.register(ProviderStage(openai_base_url=PROVIDER, api_key="k", timeout=5.0))
    ctx = ProcessingContext(
        request_id="free-text", tenant_id="default", context_id="free-text",
        original_request=request,
    )
    ctx = await pipeline.run(ctx)
    assert not ctx.errors, ctx.errors
    assert route.called

    sent = route.calls.last.request.content.decode("utf-8")
    forwarded = json.loads(sent)
    leaked = [
        (path, value)
        for path, value in _string_leaves(forwarded)
        if any(p in value for p in planted)
    ]
    assert leaked == []
    for value in planted:
        assert value not in sent
    # Structure survives: image part and tool name are untouched.
    assert forwarded["messages"][2]["content"][1]["image_url"]["url"] == "https://img.example/x.png"
    assert forwarded["tools"][0]["function"]["name"] == "crm_create"
