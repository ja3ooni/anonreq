"""Restorer — case-insensitive token→value replacement in response text.

Per PIPE-04, SSE-04, SSE-05:
- Scans LLM response text for ``[TYPE_N]`` token patterns
- Replaces each with its original value from the mapping
- Token matching is case-insensitive per SSE-04
- One substitution pass; longer tokens are matched before shorter ones
  (e.g. ``[NAME_10]`` before ``[NAME_1]``)
- Replacement values are not scanned, so token chains do not resolve
"""

from __future__ import annotations

import copy
import re
from typing import Any


class Restorer:
    """Restores tokens to original values in LLM responses.

    Usage::

        mapping = {"[EMAIL_0]": "user@example.com"}
        restored = Restorer.restore_text("Contact [EMAIL_0]", mapping)
        # → "Contact user@example.com"
    """

    @staticmethod
    def restore_text(text: str, mapping: dict[str, str]) -> str:
        """Replace all ``[TYPE_N]`` tokens with original values.

        One substitution pass, case-insensitive per SSE-04/SSE-05.
        Longer tokens are tried first so ``[NAME_10]`` is not eaten by
        ``[NAME_1]``. Replacement text is inserted literally and is not
        scanned again, so a value that itself looks like a token is not
        resolved further.

        Args:
            text: The text potentially containing ``[TYPE_N]`` tokens.
            mapping: Dict mapping token strings to original values.

        Returns:
            Text with each original token replaced once.
        """
        if not mapping or not text:
            return text

        # Empty keys would compile to an empty alternative that matches
        # everywhere; drop them.
        lookup = {token.casefold(): value for token, value in mapping.items() if token}
        if not lookup:
            return text
        # Longer tokens first. ``re`` tries alternatives left to right, so
        # ``[NAME_10]`` wins over ``[NAME_1]`` at the same position.
        ordered = sorted(lookup, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(token) for token in ordered), re.IGNORECASE)

        def replace(match: re.Match[str]) -> str:
            # Return the value as a literal. ``re.sub`` does not scan it.
            return lookup.get(match.group(0).casefold(), match.group(0))

        return pattern.sub(replace, text)

    @staticmethod
    def restore_response(
        response: dict[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Restore tokens in a full LLM response dict.

        Handles:
        - ``choices[].message.content`` (string)
        - ``choices[].message.tool_calls[].function.arguments`` (string)
        - Recursively walks string values in nested content structures

        Args:
            response: The raw provider response dict.
            mapping: Dict mapping token strings to original values.

        Returns:
            A new dict with all tokens replaced by original values.
        """
        if not mapping:
            return response

        # One deep copy, then one walk. A second pass over ``choices`` would
        # restore tokens that the first pass just inserted.
        copied = copy.deepcopy(response)
        return {key: Restorer._restore_once(value, mapping) for key, value in copied.items()}

    @staticmethod
    def _restore_once(value: Any, mapping: dict[str, str]) -> Any:
        """Restore each string exactly once. Nested containers are copied by the caller."""
        if isinstance(value, str):
            return Restorer.restore_text(value, mapping)
        if isinstance(value, dict):
            return {key: Restorer._restore_once(item, mapping) for key, item in value.items()}
        if isinstance(value, list):
            return [Restorer._restore_once(item, mapping) for item in value]
        return value
