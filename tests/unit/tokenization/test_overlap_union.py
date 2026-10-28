"""Tokenizer merges overlapping spans into their union (no character leaks)."""

from __future__ import annotations

from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer


def _tok() -> Tokenizer:
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    return tokenizer


def _span(entity_type: str, start: int, end: int, **extra: object) -> dict[str, object]:
    return {"entity_type": entity_type, "start": start, "end": end, "score": 1.0, **extra}


def test_partial_overlap_masks_union() -> None:
    text = "0123456789 tail"
    out, mapping = _tok().tokenize(text, [_span("PERSON", 0, 5), _span("EMAIL_ADDRESS", 3, 10)])
    assert out.endswith(" tail")
    for ch in "0123456789":
        assert ch not in out.split("_")[0]
    assert "56789" not in out
    assert list(mapping.values()) == ["0123456789"]
    assert Restorer.restore_text(out, mapping) == text


def test_chain_of_overlaps_masks_union() -> None:
    text = "0123456789abcdef!"
    out, _ = _tok().tokenize(
        text, [_span("A", 0, 5), _span("B", 3, 9), _span("C", 8, 16)]
    )
    assert out.endswith("!")
    assert "0123456789abcdef"[5:] not in out
    assert out.count("[") == 1


def test_union_with_secret_is_irreversible() -> None:
    text = "user hunter2pass end"
    out, mapping = _tok().tokenize(
        text, [_span("PERSON", 0, 9), _span("API_KEY", 5, 16, reversible=False)]
    )
    assert "hunter2pass" not in out
    assert mapping == {}


def test_same_value_secret_and_pii_get_distinct_tokens() -> None:
    tokenizer = _tok()
    _, secret_map = tokenizer.tokenize("k=abc", [_span("API_KEY", 2, 5, reversible=False)])
    _, pii_map = tokenizer.tokenize("n=abc", [_span("PERSON", 2, 5)])
    assert secret_map == {}
    assert list(pii_map.values()) == ["abc"]
    token = next(iter(pii_map))
    # The secret's token is not restorable via the ordinary mapping.
    secret_out, _ = tokenizer.tokenize("k=abc", [_span("API_KEY", 2, 5, reversible=False)])
    assert token not in secret_out


def test_restore_ignores_empty_keys() -> None:
    assert Restorer.restore_text("hello [A_1]", {"": "X", "[A_1]": "v"}) == "hello v"
    assert Restorer.restore_text("hello", {"": "X"}) == "hello"
