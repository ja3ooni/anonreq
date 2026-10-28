"""Single-pass tokenization and chain-resistant restoration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer

_CHAIN = {
    "[A_1]": "[B_2]",
    "[B_2]": "SECRET",
}


def test_overlapping_spans_are_applied_once() -> None:
    """Overlapping spans are replaced once, as their union (nothing leaks)."""
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenizer._seed = 0
    text = "abcdefghij"
    tokenized, mapping = tokenizer.tokenize(
        text,
        [
            {"entity_type": "PERSON", "start": 0, "end": 6, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 4, "end": 10, "score": 1.0},
        ],
    )

    assert tokenized == "[PERSON_0]"
    assert list(mapping.values()) == ["abcdefghij"]
    assert Restorer.restore_text(tokenized, mapping) == "abcdefghij"


def test_restore_text_does_not_resolve_token_chains() -> None:
    """A replacement that looks like a token is left in place."""
    restored = Restorer.restore_text("value [A_1] and [B_2]", _CHAIN)
    assert restored == "value [B_2] and SECRET"


def test_restore_response_substitutes_each_string_once() -> None:
    """Choices are restored once, so a chained value is not resolved further."""
    calls: list[str] = []
    original = Restorer.restore_text

    def spy(text: str, mapping: dict[str, str]) -> str:
        calls.append(text)
        return original(text, mapping)

    Restorer.restore_text = staticmethod(spy)  # type: ignore[method-assign]
    try:
        response = {
            "id": "chatcmpl-1",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "value [A_1] and [B_2]",
                        "tool_calls": [
                            {"function": {"arguments": '{"to": "[A_1]"}'}}
                        ],
                    }
                }
            ],
        }
        restored = Restorer.restore_response(response, _CHAIN)
    finally:
        Restorer.restore_text = original  # type: ignore[method-assign]

    content = restored["choices"][0]["message"]["content"]
    arguments = restored["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    assert content == "value [B_2] and SECRET"
    assert arguments == '{"to": "[B_2]"}'
    assert calls.count("value [A_1] and [B_2]") == 1
    assert calls.count('{"to": "[A_1]"}') == 1
    assert "value [B_2] and SECRET" not in calls
    assert response["choices"][0]["message"]["content"] == "value [A_1] and [B_2]"


@pytest.mark.asyncio
async def test_tokenization_stage_uses_a_fresh_tokenizer_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting a tokenizer must not reuse session state across requests."""
    created: list[Tokenizer] = []
    real = Tokenizer

    class _Tracking(real):
        def __init__(self) -> None:
            super().__init__()
            created.append(self)

    monkeypatch.setattr("anonreq.pipeline.tokenization.Tokenizer", _Tracking)
    stage = TokenizationStage(cache_manager=MagicMock())

    async def _run(value: str) -> None:
        ctx = ProcessingContext(
            request_id="req",
            classification_result={"action": "ANONYMIZE"},
        )
        ctx.original_request = {"messages": [{"role": "user", "content": value}]}
        ctx.text_nodes = [{"path": "messages[0].content", "value": value}]
        ctx.detections = [
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": 0,
                "end": len(value),
                "score": 1.0,
                "node_index": 0,
            }
        ]
        await stage.execute(ctx)

    await _run("a@example.com")
    await _run("b@example.com")

    assert len(created) == 2
    assert created[0] is not created[1]
    assert created[0].get_mapping() != created[1].get_mapping()
