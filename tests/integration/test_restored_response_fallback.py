"""Non-streaming response selection when restored_response is empty."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response

from anonreq.routing import chat as chat_module

_PROVIDER = {
    "id": "x",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "Hi [PERSON_7]"},
         "finish_reason": "stop"}
    ],
}


class _Pipeline:
    def __init__(self, restored: Any, provider: Any) -> None:
        self._restored = restored
        self._provider = provider

    async def run(self, proc_ctx: Any) -> Any:
        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.restored_response = self._restored
        proc_ctx.provider_response = self._provider
        return proc_ctx


async def _call(monkeypatch: pytest.MonkeyPatch, restored: Any, provider: Any) -> Any:
    state = SimpleNamespace(pipeline=_Pipeline(restored, provider))
    monkeypatch.setattr(chat_module, "get_app_state", lambda _app: state)
    monkeypatch.setattr(
        chat_module,
        "_new_processing_context",
        lambda *_a, **_k: chat_module.ProcessingContext(request_id="r"),
    )
    request = SimpleNamespace(app=None, state=SimpleNamespace())
    body = SimpleNamespace(stream=False)
    return await chat_module.chat_completions(body, request, Response(), ctx=SimpleNamespace())


@pytest.mark.asyncio
async def test_empty_restored_response_falls_back_to_tokenized_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _call(monkeypatch, {}, _PROVIDER)
    # Fallback is the provider's (tokenized) response, never raw input.
    assert result["choices"][0]["message"]["content"] == "Hi [PERSON_7]"


@pytest.mark.asyncio
async def test_no_response_at_all_is_500(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as info:
        await _call(monkeypatch, {}, None)
    assert info.value.status_code == 500
