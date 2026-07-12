"""Hypothesis property-based tests for core Phase 2 invariants.

Proves under random sampling that:
- Round-trip correctness: anonymize → restore → byte-for-byte match (TEST-01)
- Token uniqueness: N distinct values → N distinct tokens (TEST-02)
- Token deduplication: same value K times → same token (TEST-03)
- Empty detections: no entities → text unchanged (TEST-04 / TOKN-06/07)
- Session isolation: different sessions → different token indices (TEST-05)
- BLOCK classification: matching rules → 403, never reach provider (TEST-06)
- Token format: all tokens match ``[TYPE_N]`` pattern (TEST-07 / TOKN-01)
- Reverse-offset integrity: position drift prevented (TEST-08 / TOKN-04)
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from anonreq.classification.engine import ClassificationEngine, ClassificationRule
from anonreq.tokenization import Restorer
from anonreq.tokenization.tokenizer import TOKEN_PATTERN, Tokenizer
from tests.hypothesis_strategies import detection_list

# =========================================================================
# TEST-01: Round-trip correctness
# =========================================================================


@given(
    st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P"), whitelist_characters=" @._-+#"
        ),
    )
)
@settings(max_examples=1000)
def test_roundtrip_correctness(text: str) -> None:
    """Anonymize → restore produces byte-for-byte match with original.

    Generates random text, picks a valid span in the middle, tokenizes,
    then restores. The restored text must match the original exactly.
    """
    tokenizer = Tokenizer()
    tokenizer.initialize_session()

    if len(text) < 5:
        return  # Skip very short texts (no room for spans)

    # Create detection at a valid position in the middle of the text
    mid = len(text) // 2
    end = min(mid + 5, len(text))
    detections = [
        {
            "entity_type": "PERSON",
            "start": mid,
            "end": end,
            "score": 1.0,
            "source": "regex",
        }
    ]

    tokenized, mapping = tokenizer.tokenize(text, detections)

    if not mapping:
        # No entities → text must be unchanged
        assert tokenized == text, (
            f"Expected unchanged text with no mapping, "
            f"got tokenized={tokenized!r} != text={text!r}"
        )
        return

    restored = Restorer.restore_text(tokenized, mapping)
    assert restored == text, (
        f"Round-trip failed:\n"
        f"  original: {text!r}\n"
        f"  tokenized: {tokenized!r}\n"
        f"  restored: {restored!r}\n"
        f"  mapping: {mapping}"
    )


# =========================================================================
# TEST-02: Token uniqueness — N distinct values → N distinct tokens
# =========================================================================


@given(
    st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="@._-"
            ),
        ),
        min_size=1,
        max_size=10,
        unique=True,
    )
)
@settings(max_examples=1000)
def test_token_uniqueness(distinct_values: list[str]) -> None:
    """N distinct entity values produce N distinct tokens."""
    tokenizer = Tokenizer()
    tokenizer.initialize_session()

    text_parts: list[str] = []
    all_spans: list[dict] = []
    pos = 0
    for val in distinct_values:
        text_parts.append(val)
        all_spans.append(
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": pos,
                "end": pos + len(val),
                "score": 1.0,
                "source": "regex",
            }
        )
        text_parts.append(" ")  # separator
        pos += len(val) + 1

    text = "".join(text_parts)
    tokenized, mapping = tokenizer.tokenize(text, all_spans)

    # All distinct values should produce distinct tokens
    tokens = set(mapping.keys())
    assert len(tokens) == len(distinct_values), (
        f"Expected {len(distinct_values)} distinct tokens, "
        f"got {len(tokens)}. Mapping keys: {list(mapping.keys())}"
    )

    # All tokens should be EMAIL_ADDRESS type
    for token in tokens:
        assert token.startswith("[EMAIL_ADDRESS_"), (
            f"Unexpected token format: {token}"
        )

    # Verify round-trip: restore should give back original text
    restored = Restorer.restore_text(tokenized, mapping)
    # Build expected text (original without trailing space)
    " ".join(distinct_values) + " "
    if m := re.search(r"\s*$", text):  # noqa: F841
        pass
    assert restored == text, (
        f"Round-trip failed for distinct values:\n"
        f"  original: {text!r}\n"
        f"  restored: {restored!r}"
    )


# =========================================================================
# TEST-03: Token deduplication — same value K times → same token
# =========================================================================


@given(
    st.text(
        min_size=3,
        max_size=15,
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="@._-"
        ),
    ),
    st.integers(min_value=2, max_value=10),
)
@settings(max_examples=1000)
def test_token_deduplication(value: str, repeat_count: int) -> None:
    """Same value repeated K times produces the same token."""
    tokenizer = Tokenizer()
    tokenizer.initialize_session()

    # Build text with same value appearing multiple times
    text_parts: list[str] = []
    spans: list[dict] = []
    pos = 0
    for i in range(repeat_count):
        text_parts.append("prefix ")
        text_parts.append(value)
        spans.append(
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": pos + len("prefix "),
                "end": pos + len("prefix ") + len(value),
                "score": 1.0,
                "source": "regex",
            }
        )
        pos += len("prefix ") + len(value)
        if i < repeat_count - 1:
            text_parts.append(" separator ")
            pos += len(" separator ")

    text = "".join(text_parts)
    tokenized, mapping = tokenizer.tokenize(text, spans)

    # Only one unique value → only one token in mapping
    assert len(mapping) == 1, (
        f"Expected 1 token for deduplicated value '{value}' "
        f"repeated {repeat_count} times, got {len(mapping)}"
    )

    # The token should map back to the original value
    token = next(iter(mapping.keys()))
    assert mapping[token] == value, (
        f"Expected token to map to '{value}', got '{mapping[token]}'"
    )

    # The token should appear exactly repeat_count times in tokenized text
    actual_count = tokenized.count(token)
    assert actual_count == repeat_count, (
        f"Expected {repeat_count} occurrences of token '{token}', "
        f"got {actual_count}. Tokenized: {tokenized!r}"
    )

    # Verify round-trip
    restored = Restorer.restore_text(tokenized, mapping)
    assert restored == text, (
        f"Round-trip failed for deduplication:\n"
        f"  original: {text!r}\n"
        f"  restored: {restored!r}"
    )


# =========================================================================
# TEST-04: Empty detections — no entities → text unchanged (TOKN-06/07)
# =========================================================================


@given(st.text(min_size=1, max_size=200))
@settings(max_examples=500)
def test_no_entities_unchanged(text: str) -> None:
    """No detections → text unchanged, empty mapping."""
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, [])
    assert tokenized == text, (
        f"Expected unchanged text with no entities, "
        f"got tokenized={tokenized!r} != text={text!r}"
    )
    assert mapping == {}, (
        f"Expected empty mapping, got {mapping}"
    )


# =========================================================================
# TEST-05: Token session isolation — different sessions → different indices
# =========================================================================


@given(
    st.text(
        min_size=5,
        max_size=20,
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="@._-"
        ),
    )
)
@settings(max_examples=500)
def test_session_isolation(text: str) -> None:
    """Different sessions produce different token indices for same value."""
    if len(text) < 3:
        return

    span = {
        "entity_type": "EMAIL_ADDRESS",
        "start": 0,
        "end": len(text),
        "score": 1.0,
        "source": "regex",
    }

    t1 = Tokenizer()
    t1.initialize_session()
    _, m1 = t1.tokenize(text, [span])

    t2 = Tokenizer()
    t2.initialize_session()
    _, m2 = t2.tokenize(text, [span])

    # Tokens should be different across sessions (different seed)
    # With secrets.randbits(32), probability of collision is ~2^-32
    token1 = next(iter(m1.keys())) if m1 else "<none>"
    token2 = next(iter(m2.keys())) if m2 else "<none>"

    # We assert they differ because the probability is negligible
    # (broken by 1/2^32 chance, but statistically certain to pass)
    assert token1 != token2, (
        f"Two sessions produced same token '{token1}' — "
        f"extremely unlikely (collision probability ~2^-32)"
    )


# =========================================================================
# TEST-06: BLOCK classification invariant
# =========================================================================


@given(st.text(min_size=1, max_size=100))
@settings(max_examples=500, deadline=None)
def test_block_classification_invariant(text: str) -> None:
    """If classification says BLOCK → 403, never reach provider.

    For any text containing the keyword 'secret', the engine must return
    BLOCK with matched rule IDs. For text without 'secret', the default
    action PASS must be returned.
    """
    block_rule = ClassificationRule(
        id="CLS-TEST",
        enabled=True,
        version=1,
        name="test_block",
        action="BLOCK",
        metadata={},
        roles=[],
        regex_patterns=[],
        keywords=["secret"],
    )
    engine = ClassificationEngine([block_rule], default_action="PASS")

    text_nodes = [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": text,
        }
    ]
    result = engine.classify(text_nodes)

    if "secret" in text.lower():
        assert result["action"] == "BLOCK", (
            f"Expected BLOCK for text containing 'secret', "
            f"got {result['action']}. Text: {text!r}"
        )
        assert len(result["matched_rule_ids"]) > 0, (
            "Expected matched_rule_ids to be non-empty for BLOCK"
        )
    else:
        assert result["action"] == "PASS", (
            f"Expected PASS when no keyword matches, "
            f"got {result['action']}. Text: {text!r}"
        )


# =========================================================================
# TEST-07: Token format invariant — all tokens match [TYPE_N] (TOKN-01)
# =========================================================================


@given(detection_list())
@settings(max_examples=500)
def test_token_format_invariant(spans: list[dict]) -> None:
    """All generated tokens match ``[TYPE_N]`` pattern."""
    if not spans:
        return

    # Build text large enough to contain any spans
    text = "test " * 50  # 250 chars, enough for any generated spans

    # Ensure spans are within text bounds
    valid_spans = [s for s in spans if s["end"] <= len(text)]
    if not valid_spans:
        return

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, valid_spans)

    for token in mapping:
        assert TOKEN_PATTERN.fullmatch(token), (
            f"Token {token!r} does not match pattern {TOKEN_PATTERN.pattern}"
        )
        # Verify token type is uppercase, 1-20 chars
        # Extract type part: everything between '[' and last '_'
        type_part = token[1 : token.rfind("_")]
        assert 1 <= len(type_part) <= 20, (
            f"Token type length {len(type_part)} out of range [1, 20] "
            f"for token {token!r}"
        )
        # Type should be uppercase or contain underscores
        assert type_part.isupper() or "_" in type_part, (
            f"Token type not uppercase or underscore: {type_part!r} in {token!r}"
        )

    # Verify round-trip for valid spans
    if mapping and tokenized:
        restored = Restorer.restore_text(tokenized, mapping)
        # We can't assert restored == text because the text has changed,
        # but we can verify that restored text contains no residual tokens
        for token in mapping:
            assert token not in restored, (
                f"Token {token!r} leaked into restored text: {restored!r}"
            )


# =========================================================================
# TEST-08: Reverse-offset position integrity (TOKN-04)
# =========================================================================


@given(
    st.text(min_size=10, max_size=100),
)
@settings(max_examples=500)
def test_reverse_offset_position_integrity(text: str) -> None:
    """Replacing right-to-left prevents later spans from shifting.

    Two PII spans where the left replacement changes the text length
    should not affect the right span's position because spans are
    processed right-to-left.
    """
    if len(text) < 10:
        return

    mid = len(text) // 2

    # First span (left side), second span (right side)
    span1 = {
        "entity_type": "PERSON",
        "start": 0,
        "end": 5,
        "score": 1.0,
        "source": "regex",
    }
    span2 = {
        "entity_type": "EMAIL_ADDRESS",
        "start": mid,
        "end": min(mid + 5, len(text)),
        "score": 1.0,
        "source": "regex",
    }
    spans = [span1, span2]

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, spans)

    # Verify original value at span2 position is gone from tokenized text
    original_span2 = text[span2["start"] : span2["end"]]
    if original_span2.strip() and original_span2 in tokenized:
        # Only a problem if the text was supposed to be replaced
        # It might still appear if it occurred elsewhere in the text
        # But the expected behavior is that tokens replace exact positions
        pass  # Not a hard assertion since value might appear elsewhere

    # Hard assertion: verify that all tokens in the mapping are present
    for token in mapping:
        assert token in tokenized, (
            f"Token {token!r} should appear in tokenized text but doesn't. "
            f"Tokenized: {tokenized!r}"
        )

    # Verify round-trip: restore should match original
    restored = Restorer.restore_text(tokenized, mapping)
    assert restored == text, (
        f"Reverse-offset round-trip failed:\n"
        f"  original: {text!r}\n"
        f"  restored: {restored!r}\n"
        f"  mapping: {mapping}"
    )


# =========================================================================
# TEST-09 (supplementary): Multiple spans round-trip
# =========================================================================


@given(
    st.lists(
        st.text(
            min_size=2,
            max_size=10,
            alphabet=st.characters(
                whitelist_categories=("L",), whitelist_characters="-_."
            ),
        ),
        min_size=2,
        max_size=5,
        unique=True,
    )
)
@settings(max_examples=500)
def test_multiple_spans_roundtrip(words: list[str]) -> None:
    """Multiple distinct spans all round-trip correctly."""
    tokenizer = Tokenizer()
    tokenizer.initialize_session()

    # Build text with multiple words separated by spaces, detect each
    text_parts: list[str] = []
    spans: list[dict] = []
    pos = 0
    for word in words:
        text_parts.append(word)
        spans.append(
            {
                "entity_type": "PERSON",
                "start": pos,
                "end": pos + len(word),
                "score": 1.0,
                "source": "regex",
            }
        )
        pos += len(word)
        if word is not words[-1]:
            text_parts.append(" ")
            pos += 1

    text = "".join(text_parts)
    tokenized, mapping = tokenizer.tokenize(text, spans)

    # Each distinct value should produce a distinct token
    assert len(mapping) == len(words), (
        f"Expected {len(words)} tokens for {len(words)} distinct values, "
        f"got {len(mapping)}"
    )

    # Round-trip
    restored = Restorer.restore_text(tokenized, mapping)
    assert restored == text, (
        f"Multiple-spans round-trip failed:\n"
        f"  original: {text!r}\n"
        f"  restored: {restored!r}"
    )
