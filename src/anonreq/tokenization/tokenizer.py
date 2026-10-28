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



def _is_reversible(span: dict[str, Any]) -> bool:
    """Return False when a span must never be restored."""
    return bool(span.get("reversible", True))


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
        self._value_to_token: dict[tuple[str, bool], str] = {}
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
        2. Keep a non-overlapping set of spans, ordered left to right.
           A later span that overlaps an earlier one is dropped rather than
           applied with offsets from a string that has already changed.
        3. Build the result in one pass over that set:
           a. Extract the original value from the **original** ``text``.
           b. Check the deduplication map (TOKN-02).
           c. If new: truncate entity type to 20 chars (TOKN-01), compute
              index from seed + counter (TOKN-05), generate token, store
              in dedup map and output mapping.
           d. Append the untouched gap and the token. Offsets always refer
              to ``text``, never to a partially replaced copy.

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

        accepted = self._non_overlapping(text, detections)
        mapping: dict[str, str] = {}
        pieces: list[str] = []
        cursor = 0
        for span in accepted:
            start = int(span["start"])
            end = int(span["end"])
            pieces.append(text[cursor:start])
            pieces.append(self._token_for(text[start:end], span, mapping))
            cursor = end
        pieces.append(text[cursor:])
        return "".join(pieces), mapping

    @staticmethod
    def _non_overlapping(
        text: str,
        detections: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return non-overlapping spans, in left-to-right order.

        Invalid spans are ignored. Overlapping spans are merged into one
        span covering their union, so no character of either span is left
        in clear text. The merged span keeps the earliest (on a tie, the
        longest) span's type and is irreversible if any part was.
        """
        valid: list[dict[str, Any]] = []
        text_len = len(text)
        for span in detections:
            try:
                start = int(span["start"])
                end = int(span["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if start < 0 or end < 0 or start >= end or end > text_len:
                continue
            valid.append(span)

        valid.sort(key=lambda span: (int(span["start"]), -int(span["end"])))
        accepted: list[dict[str, Any]] = []
        for span in valid:
            start, end = int(span["start"]), int(span["end"])
            if accepted and start < int(accepted[-1]["end"]):
                last = accepted[-1]
                merged = {**last, "end": max(int(last["end"]), end)}
                if not _is_reversible(last) or not _is_reversible(span):
                    merged["reversible"] = False
                if last.get("protected") or span.get("protected"):
                    merged["protected"] = True
                accepted[-1] = merged
                continue
            accepted.append(span)
        return accepted

    def _token_for(
        self,
        original_value: str,
        span: dict[str, Any],
        mapping: dict[str, str],
    ) -> str:
        """Return the session token for ``original_value``, creating it if needed."""
        # Key on reversibility too: the same text seen once as a secret and
        # once as ordinary PII must not share a token, or the secret would
        # become restorable through the ordinary span's mapping entry.
        reversible = _is_reversible(span)
        key = (original_value, reversible)
        token = self._value_to_token.get(key)
        if token is None:
            entity_type_short = str(span["entity_type"])[:20]
            counter = self._per_type_counters.get(entity_type_short, 0)
            # TOKN-05: Token index = seed offset + counter.
            # Use all 32 bits of the seed (0xFFFFFFFF) for maximum
            # collision resistance. Per-pair collision probability
            # is 1/2³² ≈ 2.3·10⁻¹⁰, satisfying P ≤ 2⁻³² bound.
            token_index = (self._seed & 0xFFFFFFFF) + counter
            token = f"[{entity_type_short}_{token_index}]"
            self._value_to_token[key] = token
            self._per_type_counters[entity_type_short] = counter + 1
            if reversible:
                mapping[token] = original_value
        return token

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_mapping(self) -> dict[str, str]:
        """Return a copy of the current session's value→token mapping.

        The returned ``dict`` is a shallow copy; mutating it does not
        affect internal state.
        """
        return {value: token for (value, _), token in self._value_to_token.items()}
