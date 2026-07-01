"""Restorer — case-insensitive token→value replacement in response text.

Per PIPE-04, SSE-04, SSE-05:
- Scans LLM response text for ``[TYPE_N]`` token patterns
- Replaces each with its original value from the mapping
- Token matching is case-insensitive per SSE-04
- Tokens are sorted by length descending to prevent partial collisions
  (e.g. ``[NAME_10]`` replaced before ``[NAME_1]``)
"""

from __future__ import annotations

import re
from typing import Any

from anonreq.models.tokenization import TOKEN_PATTERN


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

        Case-insensitive matching per SSE-04/SSE-05.
        Tokens sorted by length descending to avoid partial collisions
        (e.g. ``[NAME_10]`` replaced before ``[NAME_1]``).

        Args:
            text: The text potentially containing ``[TYPE_N]`` tokens.
            mapping: Dict mapping token strings to original values.

        Returns:
            Text with all tokens replaced by their original values.
        """
        if not mapping or not text:
            return text

        # Sort tokens by length descending for safe replacement
        sorted_tokens = sorted(mapping.keys(), key=len, reverse=True)

        result = text
        for token in sorted_tokens:
            original = mapping[token]
            # Case-insensitive match per SSE-04
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            # Use lambda to prevent re.sub from interpreting backreference
            # escapes (\1, \A, \000, etc.) in the replacement value.
            # Without this, an original value like "\1" would be interpreted
            # as a group reference, causing re.error or incorrect output.
            result = pattern.sub(lambda m: original, result)

        return result

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

        restored: dict[str, Any] = {}
        for key, value in response.items():
            if isinstance(value, str):
                restored[key] = Restorer.restore_text(value, mapping)
            elif isinstance(value, dict):
                restored[key] = Restorer.restore_response(value, mapping)
            elif isinstance(value, list):
                restored[key] = [
                    Restorer.restore_response(item, mapping)
                    if isinstance(item, dict)
                    else Restorer.restore_text(item, mapping)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                restored[key] = value

        # Specific handling for OpenAI response structure:
        # Deep-copy won't help with the nested choices[].message.content
        # since the recursive walk above already handles it. But we also
        # specifically walk the known OpenAI response path for clarity.
        if "choices" in response and isinstance(response["choices"], list):
            restored_choices: list[dict[str, Any]] = []
            for choice in response["choices"]:
                if isinstance(choice, dict):
                    rc = choice.copy()
                    if "message" in rc and isinstance(rc["message"], dict):
                        msg = rc["message"]
                        if "content" in msg and isinstance(msg["content"], str):
                            msg["content"] = Restorer.restore_text(
                                msg["content"], mapping
                            )
                        if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                            for tc in msg["tool_calls"]:
                                if isinstance(tc, dict) and "function" in tc:
                                    fn = tc["function"]
                                    if "arguments" in fn and isinstance(fn["arguments"], str):
                                        fn["arguments"] = Restorer.restore_text(
                                            fn["arguments"], mapping
                                        )
                    restored_choices.append(rc)
                else:
                    restored_choices.append(choice)
            restored["choices"] = restored_choices

        return restored
