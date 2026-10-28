"""TextExtractor fails closed on schemas it cannot fully scan."""

from __future__ import annotations

from typing import Any

import pytest

from anonreq.pipeline.extraction import MAX_SCHEMA_DEPTH, TextExtractor, UnscannableRequestError


def _body(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "m",
        "messages": [{"role": "user", "content": "x"}],
        "tools": [{"type": "function", "function": {"name": "f", "parameters": parameters}}],
    }


def _nested(levels: int) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": "deep secret"}
    for _ in range(levels):
        schema = {"type": "object", "properties": {"p": schema}}
    return schema


def test_schema_at_max_depth_is_scanned() -> None:
    nodes = TextExtractor.extract(_body(_nested(MAX_SCHEMA_DEPTH)))
    assert any(n["value"] == "deep secret" for n in nodes)


def test_schema_deeper_than_max_depth_is_rejected() -> None:
    with pytest.raises(UnscannableRequestError) as exc:
        TextExtractor.extract(_body(_nested(MAX_SCHEMA_DEPTH + 1)))
    assert exc.value.status_code == 400


@pytest.mark.parametrize("key", ["a.b", "a[0]", "x]"])
def test_unwritable_property_name_is_rejected(key: str) -> None:
    params = {"type": "object", "properties": {key: {"type": "string", "description": "d"}}}
    with pytest.raises(UnscannableRequestError):
        TextExtractor.extract(_body(params))
