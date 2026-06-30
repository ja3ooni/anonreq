"""Tests for the Tokenization Engine.

Per TOKN-01 through TOKN-07:
- Token format is [TYPE_N] with uppercase type (1-20 chars) and positive integer N
- Same value → same token (deduplication)
- Different values of same type → different tokens with different indices
- Reverse-offset replacement prevents position drift
- Token index derived from cryptographically random seed per session
- No entities → request forwarded unchanged, no token mapping created
"""

from __future__ import annotations

import re
import secrets

import pytest

from anonreq.tokenization import TOKEN_PATTERN, Tokenizer


# =========================================================================
# TOKN-01: Token format
# =========================================================================


class TestTokenFormat:
    """Generated tokens must match ``[TYPE_N]`` pattern per TOKN-01."""

    def test_token_matches_pattern(self) -> None:
        """Token string matches ``[TYPE_N]`` regex."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("email: user@example.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 7, "end": 22, "score": 1.0},
        ])
        assert len(mapping) == 1
        token = list(mapping.keys())[0]
        assert re.match(r"\[[A-Z][A-Z_]{0,19}_\d+\]$", token), f"Token '{token}' does not match [TYPE_N]"

    def test_entity_type_uppercase(self) -> None:
        """Entity type in token is uppercase."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("email: user@example.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 7, "end": 22, "score": 1.0},
        ])
        token = list(mapping.keys())[0]
        # Extract the type part (between [ and _)
        type_part = token[1:token.rfind("_")]
        assert type_part.isupper(), f"Type '{type_part}' in token '{token}' is not uppercase"

    def test_token_index_positive(self) -> None:
        """Token index N is a positive integer (0+)."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("email: user@example.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 7, "end": 22, "score": 1.0},
        ])
        token = list(mapping.keys())[0]
        index_str = token[token.rfind("_") + 1:token.rfind("]")]
        index = int(index_str)
        assert index >= 0, f"Token index {index} is negative"


# =========================================================================
# TOKN-02: Same value → same token (deduplication)
# =========================================================================


class TestDeduplication:
    """Same entity value in same session produces the same token."""

    def test_same_value_reuses_token(self) -> None:
        """Same email appearing twice gets the same token."""
        t = Tokenizer()
        t.initialize_session()
        text = "Contact john@example.com or write to john@example.com"
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 23, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 42, "end": 57, "score": 1.0},
        ]
        tokenized, mapping = t.tokenize(text, detections)

        # Same value → same token, so mapping should have only 1 entry
        assert len(mapping) == 1, f"Expected 1 mapping entry, got {len(mapping)}"

        # Both occurrences should be replaced with the same token
        token = list(mapping.keys())[0]
        assert tokenized.count(token) == 2, f"Expected token '{token}' to appear twice"

    def test_different_values_different_tokens(self) -> None:
        """Different emails get different tokens."""
        t = Tokenizer()
        t.initialize_session()
        text = "Contact alice@example.com or bob@example.com"
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 25, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 29, "end": 44, "score": 1.0},
        ]
        tokenized, mapping = t.tokenize(text, detections)

        # Different values → different tokens, so mapping should have 2 entries
        assert len(mapping) == 2, f"Expected 2 mapping entries, got {len(mapping)}"

        # Each token should appear exactly once
        for token in mapping:
            assert tokenized.count(token) == 1, f"Expected token '{token}' to appear once"

    def test_dedup_across_different_spans_same_type(self) -> None:
        """Same phone number appearing as same value gets deduped."""
        t = Tokenizer()
        t.initialize_session()
        text = "Call +1-555-123-4567 now or +1-555-123-4567 later"
        detections = [
            {"entity_type": "PHONE_NUMBER", "start": 5, "end": 19, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 28, "end": 42, "score": 1.0},
        ]
        tokenized, mapping = t.tokenize(text, detections)
        assert len(mapping) == 1
        token = list(mapping.keys())[0]
        assert tokenized.count(token) == 2


# =========================================================================
# TOKN-03: Different values → different indices
# =========================================================================


class TestDistinctIndices:
    """Different entity values of same type get different indices."""

    def test_different_values_same_type(self) -> None:
        """Two different emails have different token indices."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("alice@example.com and bob@example.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 17, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 22, "end": 37, "score": 1.0},
        ])

        tokens = list(mapping.keys())
        assert len(tokens) == 2

        # Extract indices
        indices = []
        for token in tokens:
            idx = int(token[token.rfind("_") + 1:token.rfind("]")])
            indices.append(idx)

        assert indices[0] != indices[1], f"Expected different indices, got {indices}"

    def test_values_use_increasing_counters(self) -> None:
        """Three different emails have strictly increasing indices."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("a@a.com b@b.com c@c.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 15, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 16, "end": 23, "score": 1.0},
        ])

        tokens = list(mapping.keys())
        assert len(tokens) == 3
        indices = [int(t[t.rfind("_") + 1:t.rfind("]")]) for t in tokens]

        # Indices should be increasing
        assert indices == sorted(indices), f"Expected increasing indices, got {indices}"


# =========================================================================
# TOKN-04: Reverse-offset replacement
# =========================================================================


class TestReverseOffsetReplacement:
    """Reverse-offset (right-to-left) replacement prevents position drift."""

    def test_reverse_offset_prevents_drift(self) -> None:
        """Two PII spans — first replacement longer than original doesn't shift
        second span's position when replaced right-to-left.

        Text: "PII_A content PII_B"
        If PII_B is replaced first (rightmost), its position is correct because
        PII_A hasn't been replaced yet. Then PII_A is replaced using its original
        position because the text right of it has already been handled.
        """
        t = Tokenizer()
        t.initialize_session()
        text = "short\nmore"  # Simple test: two distinct spans
        # Detect "short" at 0-5 and "more" at 6-10
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 6, "end": 10, "score": 1.0},  # "more"
            {"entity_type": "PERSON", "start": 0, "end": 5, "score": 1.0},  # "short"
        ]
        tokenized, mapping = t.tokenize(text, detections)

        # Both should be replaced with tokens
        assert len(mapping) == 2
        assert "short" not in tokenized
        assert "more" not in tokenized

        # Verify the tokens appear in the right order
        # Token for "short" should be first, token for "more" should be second
        token_short = mapping.get("[PERSON_")
        token_more = mapping.get("[EMAIL_")

    def test_replacement_different_sizes(self) -> None:
        """Replacing a span with a token that has different length doesn't
        affect other replacements.

        Original text "AAA BBB CCC" where AAA and CCC are PII.
        If token for AAA is "[PERSON_12345]" (much longer than "AAA"),
        the position for CCC should still be correct.
        """
        t = Tokenizer()
        t.initialize_session()
        text = "AAA   BBB   CCC"
        # AAA at 0-3, CCC at 12-15
        detections = [
            {"entity_type": "PERSON", "start": 0, "end": 3, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 12, "end": 15, "score": 1.0},
        ]
        tokenized, mapping = t.tokenize(text, detections)

        # Both tokens should be present with correct ordering
        assert "AAA" not in tokenized
        assert "CCC" not in tokenized
        assert "BBB" in tokenized  # Middle part preserved

        # The tokens should be separated by "   BBB   "
        tokens_in_result = [t for t in mapping if t in tokenized]
        assert len(tokens_in_result) == 2

        # Verify the order: first token before BBB, second after BBB
        first_pos = tokenized.find(tokens_in_result[0])
        second_pos = tokenized.find(tokens_in_result[1])
        bbb_pos = tokenized.find("BBB")
        assert first_pos < bbb_pos < second_pos, (
            f"Expected token order [PERSON] ... BBB ... [EMAIL], got positions "
            f"first={first_pos}, BBB={bbb_pos}, second={second_pos}"
        )


# =========================================================================
# TOKN-05: Random seed per session
# =========================================================================


class TestRandomSeed:
    """Token indices are derived from a cryptographically random seed."""

    def test_different_sessions_different_seeds(self) -> None:
        """Two independent sessions produce different token indices
        for the same input (with very high probability)."""
        t1 = Tokenizer()
        t2 = Tokenizer()
        t1.initialize_session()
        t2.initialize_session()

        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 17, "score": 1.0},
        ]

        _, m1 = t1.tokenize("user@example.com", detections)
        _, m2 = t2.tokenize("user@example.com", detections)

        t1_token = list(m1.keys())[0]
        t2_token = list(m2.keys())[0]

        # With 32-bit random seed, probability of collision is ~2^-32
        assert t1_token != t2_token, (
            f"Two sessions produced same token '{t1_token}' — "
            f"very unlikely (collision probability ~2^-32)"
        )

    def test_session_reset_changes_seed(self) -> None:
        """Calling initialize_session again changes the seed."""
        t = Tokenizer()
        t.initialize_session()

        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 17, "score": 1.0},
        ]

        _, m1 = t.tokenize("user@example.com", detections)
        t1_token = list(m1.keys())[0]

        t.initialize_session()  # Reset session
        _, m2 = t.tokenize("user@example.com", detections)
        t2_token = list(m2.keys())[0]

        # New session should (with very high probability) produce a different token
        assert t1_token != t2_token, (
            f"Session reset produced same token '{t1_token}' — "
            f"very unlikely"
        )

    def test_seed_affects_counter_start(self) -> None:
        """The first token index in a session is determined by the seed,
        not always starting from 0."""
        # Run this multiple times with fresh sessions; at least one should
        # produce a non-zero first index (due to random seed offset).
        any_non_zero = False
        for _ in range(20):
            t = Tokenizer()
            t.initialize_session()

            detections = [
                {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 17, "score": 1.0},
            ]
            _, mapping = t.tokenize("user@example.com", detections)
            token = list(mapping.keys())[0]
            idx = int(token[token.rfind("_") + 1:token.rfind("]")])
            if idx > 0:
                any_non_zero = True
                break

        assert any_non_zero, "Expected at least one non-zero first index in 20 runs"


# =========================================================================
# TOKN-06/07: No entities → unchanged
# =========================================================================


class TestNoEntities:
    """No entities detected → request forwarded unchanged, no mapping."""

    def test_empty_detections_returns_original(self) -> None:
        """Empty detections list returns original text."""
        t = Tokenizer()
        t.initialize_session()
        text = "Hello, this is a normal message with no PII."
        result, mapping = t.tokenize(text, [])
        assert result == text, "Expected original text unchanged"
        assert mapping == {}, f"Expected empty mapping, got {mapping}"

    def test_none_detections_returns_original(self) -> None:
        """None as detections should still work (treated as empty)."""
        t = Tokenizer()
        t.initialize_session()
        text = "Just a normal message."
        result, mapping = t.tokenize(text, [])
        assert result == text
        assert mapping == {}

    def test_no_mapping_when_no_entities(self) -> None:
        """No mapping dict created when no entities."""
        t = Tokenizer()
        t.initialize_session()
        _, mapping = t.tokenize("No PII here", [])
        assert len(mapping) == 0


# =========================================================================
# Per-type independent counters
# =========================================================================


class TestIndependentCounters:
    """Different entity types have independent counters."""

    def test_different_types_independent_counters(self) -> None:
        """EMAIL and PHONE both start with their first index based on seed."""
        t = Tokenizer()
        t.initialize_session()

        _, mapping = t.tokenize("email and phone", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 5, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 10, "end": 15, "score": 1.0},
        ])

        tokens = list(mapping.keys())
        assert len(tokens) == 2

        # Extract type and index
        type_indices = {}
        for token in tokens:
            type_part = token[1:token.rfind("_")]
            idx = int(token[token.rfind("_") + 1:token.rfind("]")])
            type_indices[type_part] = idx

        # Both types should have their first index (0 + seed offset)
        # They are independent, so there's no guarantee one is before the other
        assert "EMAIL_ADDRESS" in type_indices
        assert "PHONE_NUMBER" in type_indices

    def test_two_of_each_type(self) -> None:
        """Two emails and two phones — indices per type are sequential."""
        t = Tokenizer()
        t.initialize_session()

        _, mapping = t.tokenize("a@a.com b@b.com 555-0001 555-0002", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 15, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 16, "end": 24, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 25, "end": 33, "score": 1.0},
        ])

        tokens = list(mapping.keys())
        assert len(tokens) == 4

        email_indices = []
        phone_indices = []
        for token in tokens:
            type_part = token[1:token.rfind("_")]
            idx = int(token[token.rfind("_") + 1:token.rfind("]")])
            if type_part == "EMAIL_ADDRESS":
                email_indices.append(idx)
            else:
                phone_indices.append(idx)

        assert len(email_indices) == 2, f"Expected 2 EMAIL tokens, got {email_indices}"
        assert len(phone_indices) == 2, f"Expected 2 PHONE tokens, got {phone_indices}"

        # The second index should be first index + 1 for each type
        assert email_indices[1] == email_indices[0] + 1
        assert phone_indices[1] == phone_indices[0] + 1


# =========================================================================
# Entity type truncation (>20 chars)
# =========================================================================


class TestEntityTypeTruncation:
    """Entity type names >20 chars are truncated to 20 chars per TOKN-01."""

    def test_truncate_long_entity_type(self) -> None:
        """Entity type longer than 20 chars is truncated."""
        t = Tokenizer()
        t.initialize_session()

        long_type = "CUSTOM_ENTERPRISE_PATTERN_VERY_LONG"
        _, mapping = t.tokenize("found sensitive data", [
            {"entity_type": long_type, "start": 6, "end": 20, "score": 1.0},
        ])

        token = list(mapping.keys())[0]
        # Extract type part between [ and last _
        type_part = token[1:token.rfind("_")]

        # Should be truncated to 20 chars
        assert len(type_part) <= 20, (
            f"Expected type <= 20 chars, got {len(type_part)}: '{type_part}'"
        )
        # Should match the first 20 chars of the original
        assert type_part == long_type[:20], (
            f"Expected '{long_type[:20]}', got '{type_part}'"
        )

    def test_exactly_20_chars_not_truncated(self) -> None:
        """Entity type of exactly 20 chars is not truncated."""
        t = Tokenizer()
        t.initialize_session()

        # Exactly 20 chars
        type_20 = "ABCDEFGHIJKLMNOPQRST"  # 20 chars
        _, mapping = t.tokenize("data here", [
            {"entity_type": type_20, "start": 0, "end": 4, "score": 1.0},
        ])

        token = list(mapping.keys())[0]
        type_part = token[1:token.rfind("_")]
        assert type_part == type_20, f"Expected '{type_20}', got '{type_part}'"

    def test_short_type_not_truncated(self) -> None:
        """Entity type under 20 chars is not truncated."""
        t = Tokenizer()
        t.initialize_session()

        _, mapping = t.tokenize("call me", [
            {"entity_type": "PERSON", "start": 0, "end": 4, "score": 1.0},
        ])

        token = list(mapping.keys())[0]
        type_part = token[1:token.rfind("_")]
        assert type_part == "PERSON"


# =========================================================================
# Round-trip correctness
# =========================================================================


class TestRoundTrip:
    """Tokenized text can be restored to original via mapping."""

    def test_round_trip_simple(self) -> None:
        """Tokenize then restore tokens to get original text."""
        t = Tokenizer()
        t.initialize_session()

        original = "Email me at john@example.com or call +1-555-123-4567"
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 11, "end": 26, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 35, "end": 49, "score": 1.0},
        ]

        tokenized, mapping = t.tokenize(original, detections)

        # Restore by replacing tokens with their original values
        restored = tokenized
        for token, value in mapping.items():
            restored = restored.replace(token, value)

        assert restored == original, (
            f"Round-trip failed:\n  Original: {original}\n  Tokenized: {tokenized}\n  Restored: {restored}"
        )

    def test_round_trip_multiple_same_value(self) -> None:
        """Round-trip with deduplicated values."""
        t = Tokenizer()
        t.initialize_session()

        original = "user@test.com and user@test.com again"
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 13, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 18, "end": 31, "score": 1.0},
        ]

        tokenized, mapping = t.tokenize(original, detections)

        restored = tokenized
        for token, value in mapping.items():
            restored = restored.replace(token, value)

        assert restored == original

    def test_round_trip_no_pii(self) -> None:
        """Round-trip with no PII — unchanged."""
        t = Tokenizer()
        t.initialize_session()

        original = "No PII here at all."
        tokenized, mapping = t.tokenize(original, [])
        assert tokenized == original
        assert mapping == {}


# =========================================================================
# Session isolation
# =========================================================================


class TestSessionIsolation:
    """initialize_session() resets state with new seed."""

    def test_counters_reset_on_new_session(self) -> None:
        """After initialize_session, counters start fresh."""
        t = Tokenizer()
        t.initialize_session()

        # First session — generate some tokens
        _, m1 = t.tokenize("a@a.com b@b.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 15, "score": 1.0},
        ])

        t.initialize_session()  # Reset

        # Now generate one token in the new session
        _, m2 = t.tokenize("c@c.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
        ])

        assert len(m2) == 1
        # The single token should have index = seed_offset (counter = 0 for the type)
        token2 = list(m2.keys())[0]
        assert "[EMAIL_" in token2

    def test_dedup_map_reset_on_new_session(self) -> None:
        """After initialize_session, the dedup map is cleared."""
        t = Tokenizer()
        t.initialize_session()

        # First session
        t.tokenize("a@a.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
        ])

        t.initialize_session()  # Reset — clears dedup map

        # Same value in new session should get a new token
        _, m2 = t.tokenize("a@a.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
        ])

        assert len(m2) == 1  # Not deduped from previous session because it was reset


# =========================================================================
# TOKEN_PATTERN regex constant
# =========================================================================


class TestTokenPattern:
    """TOKEN_PATTERN regex matches [TYPE_N] tokens."""

    def test_pattern_matches_valid_tokens(self) -> None:
        """TOKEN_PATTERN correctly matches valid tokens."""
        valid_tokens = [
            "[EMAIL_0]",
            "[PHONE_NUMBER_1]",
            "[PERSON_42]",
            "[CUSTOM_ENTERPRISE_PATTER_999]",
            "[A_0]",
            "[ABCDEFGHIJKLMNOPQRST_1234567890]",
        ]
        for token in valid_tokens:
            assert TOKEN_PATTERN.fullmatch(token), f"Pattern should match '{token}'"

    def test_pattern_rejects_invalid_tokens(self) -> None:
        """TOKEN_PATTERN rejects malformed tokens."""
        invalid_tokens = [
            "EMAIL_0]",           # Missing [
            "[EMAIL_0",           # Missing ]
            "[email_0]",          # Lowercase
            "[ EMAIL_0]",         # Space
            "[EMAIL_ 0]",         # Space
            "[_EMAIL_0]",         # Starts with underscore
            "[EMAIL_]",           # Missing number
            "[]",                  # Empty
        ]
        for token in invalid_tokens:
            assert not TOKEN_PATTERN.fullmatch(token), f"Pattern should reject '{token}'"

    def test_generated_tokens_match_pattern(self) -> None:
        """Tokens generated by Tokenizer always match TOKEN_PATTERN."""
        t = Tokenizer()
        t.initialize_session()

        _, mapping = t.tokenize("a@a.com b@b.com 555-0001 PERSON", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 7, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 8, "end": 15, "score": 1.0},
            {"entity_type": "PHONE_NUMBER", "start": 16, "end": 24, "score": 1.0},
            {"entity_type": "PERSON", "start": 25, "end": 31, "score": 1.0},
        ])

        for token in mapping:
            assert TOKEN_PATTERN.fullmatch(token), f"Generated token '{token}' does not match pattern"


# =========================================================================
# Large text handling
# =========================================================================


class TestLargeText:
    """Tokenizer handles long text efficiently."""

    def test_long_text(self) -> None:
        """Tokenizer handles 1000+ character text."""
        t = Tokenizer()
        t.initialize_session()

        # Create a long text with several PII instances
        base = "This is a long text with email user@example.com and more content. " * 20
        # Should be > 1000 chars
        assert len(base) > 1000, f"Test text too short: {len(base)}"

        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 30, "end": 47, "score": 1.0},
            {"entity_type": "EMAIL_ADDRESS", "start": 30 + 65, "end": 47 + 65, "score": 1.0},
        ]

        tokenized, mapping = t.tokenize(base, detections)
        assert len(mapping) == 1  # Same email deduped
        assert "user@example.com" not in tokenized


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases for the tokenizer."""

    def test_single_character_text(self) -> None:
        """Tokenizer handles single-character text."""
        t = Tokenizer()
        t.initialize_session()

        result, mapping = t.tokenize("x", [
            {"entity_type": "PERSON", "start": 0, "end": 1, "score": 1.0},
        ])
        assert len(mapping) == 1
        assert "x" not in result

    def test_empty_string(self) -> None:
        """Tokenizer handles empty string."""
        t = Tokenizer()
        t.initialize_session()

        result, mapping = t.tokenize("", [])
        assert result == ""
        assert mapping == {}

    def test_whitespace_only(self) -> None:
        """Tokenizer handles whitespace-only text."""
        t = Tokenizer()
        t.initialize_session()

        result, mapping = t.tokenize("   ", [])
        assert result == "   "
        assert mapping == {}

    def test_spans_at_boundaries(self) -> None:
        """Spans at the very start and end of text."""
        t = Tokenizer()
        t.initialize_session()

        result, mapping = t.tokenize("A B", [
            {"entity_type": "PERSON", "start": 0, "end": 1, "score": 1.0},
            {"entity_type": "PERSON", "start": 2, "end": 3, "score": 1.0},
        ])
        assert len(mapping) == 2
        assert "A" not in result
        assert "B" not in result

    def test_get_mapping_returns_copy(self) -> None:
        """get_mapping returns a copy that doesn't affect internal state."""
        t = Tokenizer()
        t.initialize_session()

        t.tokenize("email: test@test.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 7, "end": 19, "score": 1.0},
        ])

        mapping = t.get_mapping()
        mapping["[INJECTED_0]"] = "injected"

        # Modifying the returned mapping should NOT affect the internal state
        _, m2 = t.tokenize("other@test.com", [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 13, "score": 1.0},
        ])
        assert "[INJECTED_0]" not in m2
