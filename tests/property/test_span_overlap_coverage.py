"""Detected characters must not survive tokenization after overlap resolution.

SpanArbiter collapses overlapping spans onto the union of their ranges.
Tokenizing that result replaces every character that belonged to any input
span, including the leftover tail of a span that lost a partial overlap.
"""

from __future__ import annotations

import re
from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from anonreq.detection.regex_patterns import ENTITY_SPECIFICITY
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer

_TOKEN = re.compile(r"\[[A-Z][A-Z_]{0,49}_\d+\]")
_ENTITY_TYPES = tuple(ENTITY_SPECIFICITY)


def _covered(spans: list[dict]) -> set[int]:
    indexes: set[int] = set()
    for span in spans:
        indexes.update(range(int(span["start"]), int(span["end"])))
    return indexes


@st.composite
def _text_and_spans(draw: st.DrawFn) -> tuple[str, list[dict]]:
    alphabet = st.characters(whitelist_categories=("L", "N"), whitelist_characters=" ")
    text = draw(st.text(alphabet=alphabet, min_size=1, max_size=48))
    count = draw(st.integers(min_value=0, max_value=6))
    spans: list[dict] = []
    for _ in range(count):
        start = draw(st.integers(min_value=0, max_value=len(text) - 1))
        end = draw(st.integers(min_value=start + 1, max_value=len(text)))
        spans.append(
            {
                "entity_type": draw(st.sampled_from(_ENTITY_TYPES)),
                "start": start,
                "end": end,
                "score": draw(st.floats(min_value=0.05, max_value=1.0, allow_nan=False)),
                "source": draw(st.sampled_from(("regex", "ner", "enterprise", "mnpi"))),
            }
        )
    return text, spans


@settings(max_examples=100, deadline=None)
@given(sample=_text_and_spans())
def test_no_detected_character_survives_tokenization(sample: tuple[str, list[dict]]) -> None:
    """Every character of every input span is replaced, and restoration is exact."""
    text, spans = sample
    merged = SpanArbiter.merge(spans, [])

    assert _covered(merged) == _covered(spans)
    ordered = sorted(merged, key=lambda item: (item["start"], item["end"]))
    for earlier, later in pairwise(ordered):
        assert later["start"] >= earlier["end"]

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    forced = [{**span, "reversible": True} for span in merged]
    tokenized, mapping = tokenizer.tokenize(text, forced)

    outside = "".join(char for index, char in enumerate(text) if index not in _covered(spans))
    assert _TOKEN.sub("", tokenized) == outside
    assert Restorer.restore_text(tokenized, mapping) == text
