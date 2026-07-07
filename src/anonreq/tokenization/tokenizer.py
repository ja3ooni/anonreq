"""Tokenization engine — core ``[TYPE_N]`` token generator.

Replaces detected PII spans with ``[TYPE_N]`` placeholders using
reverse-offset replacement to prevent position drift. Maintains per-type
atomic counters for independent index sequences and a deduplication map
so the same entity value always maps to the same token within a session.

Per TOKN-01 through TOKN-07.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

TOKEN_PATTERN = re.compile(r"\[([A-Z][A-Z_]{0,49})_(\d+)\]")
"""Regex matching a ``[TYPE_N]`` token per TOKN-01.

Groups:
    1. The entity type (uppercase, 1-50 chars)
    2. The index (positive integer)
"""


class Tokenizer:
    """Generates ``[TYPE_N]`` tokens with deduplication and random seed offsets.

    Typical usage::

        tokenizer = Tokenizer()
        tokenizer.initialize_session()
        tokenized_text, mapping = tokenizer.tokenize(
            "My email is john@example.com",
            [{"entity_type": "EMAIL_ADDRESS", "start": 11, "end": 26, "score": 1.0}],
        )
    """

    def __init__(self) -> None:
        self._per_type_counters: dict[str, int] = {}
        self._value_to_token: dict[str, str] = {}
        self._seed: int = 0

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def initialize_session(self) -> None:
        """Reset all per-session state and generate a new random seed.

        Must be called before the first ``tokenize()`` call of a session
        to ensure fresh counters and a new cryptographically random seed.
        """
        self._per_type_counters = {}
        self._value_to_token = {}
        self._seed = secrets.randbits(32)

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    def tokenize(
        self,
        text: str,
        detections: list[dict[str, Any]],
    ) -> tuple[str, dict[str, str]]:
        """Replace detected entity spans with ``[TYPE_N]`` tokens.

        Steps:
        1. If ``detections`` is empty, return ``(text, {})`` (TOKN-06/07).
        2. Sort spans descending by ``start`` position (reverse-offset per
           TOKN-04) so rightmost spans are replaced first.
        3. For each span:
           a. Extract the original value from the **original** ``text``.
           b. Check the deduplication map (TOKN-02).
           c. If new: truncate entity type to 20 chars (TOKN-01), compute
              index from seed + counter (TOKN-05), generate token, store
              in dedup map and output mapping.
           d. Slice the working ``tokenized`` string around the (original)
              span positions and insert the token.

        Args:
            text: The original text containing PII.
            detections: A list of detection dicts, each with keys
                ``entity_type``, ``start``, ``end``, ``score``, and
                optionally ``source``.

        Returns:
            A tuple of ``(tokenized_text, mapping)`` where:
            - ``tokenized_text`` is the text with all spans replaced
            - ``mapping`` is a ``{token: original_value}`` dict
        """
        if not detections:
            return text, {}

        # Sort spans descending by start position (TOKN-04: reverse-offset)
        sorted_spans = sorted(
            detections,
            key=lambda s: s["start"],
            reverse=True,
        )

        tokenized = text
        mapping: dict[str, str] = {}

        for span in sorted_spans:
            entity_type: str = span["entity_type"]
            start: int = span["start"]
            end: int = span["end"]

            # Guard against corrupted detections (T-02-03-05)
            if start < 0 or end < 0 or start >= end:
                continue

            original_value = text[start:end]

            # TOKN-02: Deduplication — same value → same token
            token = self._value_to_token.get(original_value)
            if token is None:
                # TOKN-01: Cap entity type at 20 chars
                entity_type_short = entity_type[:20]

                # Get per-type counter (default 0)
                counter = self._per_type_counters.get(entity_type_short, 0)

                # TOKN-05: Token index = seed offset + counter
                # Use all 32 bits of the seed (0xFFFFFFFF) for maximum
                # collision resistance. Per-pair collision probability
                # is 1/2³² ≈ 2.3·10⁻¹⁰, satisfying P ≤ 2⁻³² bound.
                token_index = (self._seed & 0xFFFFFFFF) + counter
                token = f"[{entity_type_short}_{token_index}]"

                self._value_to_token[original_value] = token
                self._per_type_counters[entity_type_short] = counter + 1
                mapping[token] = original_value

            # Reverse-offset replacement (spans sorted descending,
            # so earlier replacements don't shift later positions)
            before = tokenized[:start]
            after = tokenized[end:]
            tokenized = before + token + after

        return tokenized, mapping

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_mapping(self) -> dict[str, str]:
        """Return a copy of the current session's value→token mapping.

        The returned ``dict`` is a shallow copy; mutating it does not
        affect internal state.
        """
        return self._value_to_token.copy()
