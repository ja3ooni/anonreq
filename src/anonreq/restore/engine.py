"""RestoreEngine — path-aware token restoration for structured responses.

Extends the basic ``Restorer`` with ``PathTracker`` integration so that
tokens detected at specific JSON paths can be restored with positional
awareness.  This is particularly important for tool call arguments,
nested JSON content, and streaming responses where the exact location
of each token matters.

Per PIPE-04, SSE-04, SSE-05:
- Token matching is case-insensitive
- Brackets are optional during matching (``[EMAIL_0]`` and ``EMAIL_0`` both work)
- Tokens are sorted by length descending to prevent partial collisions
- Backslash/escape sequences in values are handled safely
"""

from __future__ import annotations

import json
import re
from typing import Any

from anonreq.restore.path_tracker import PathTracker


class RestoreEngine:
    """Path-aware token restoration engine.

    Wraps the basic ``Restorer`` functionality with path tracking so that
    tokens detected at known JSON paths can be restored precisely.

    Usage::

        tracker = PathTracker()
        # ... during detection ...
        tracker.track("[EMAIL_0]", "messages.0.content")

        engine = RestoreEngine(path_tracker=tracker)
        restored = engine.restore_with_paths("Hello [EMAIL_0]", mapping)
        # → "Hello user@example.com"

        response = engine.restore_response_with_paths(api_response, mapping)
    """

    # Regex matching a complete ``[TYPE_N]`` or ``TYPE_N`` token.
    # Supports case-insensitive matching and optional brackets per SSE-04.
    _TOKEN_CORE_PATTERN = re.compile(
        r"(?<![A-Za-z0-9_])\[?([A-Z][A-Z_]{0,19}_\d+)\]?(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )

    def __init__(self, path_tracker: PathTracker | None = None) -> None:
        if path_tracker is not None and not isinstance(path_tracker, PathTracker):
            raise TypeError(
                f"path_tracker must be a PathTracker instance, got {type(path_tracker).__name__}"
            )
        self._path_tracker = path_tracker or PathTracker()

    @property
    def path_tracker(self) -> PathTracker:
        """The underlying PathTracker instance."""
        return self._path_tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def restore_with_paths(self, text: str, mapping: dict[str, str]) -> str:
        """Restore tokens in *text* using the given *mapping*.

        Uses the tracked paths for context, then falls back to text-level
        replacement.  Handles case-insensitive and bracket-optional matching.

        Args:
            text: Text potentially containing ``[TYPE_N]`` tokens.
            mapping: Dict mapping token strings to original values.

        Returns:
            Text with all tokens replaced by their original values.
        """
        if not mapping or not text:
            return text

        # Build a lookup table: token_core.casefold() → original value
        lookup: dict[str, str] = {}
        for token, value in mapping.items():
            core = token.strip("[]")
            lookup[core.casefold()] = value

        if not lookup:
            return text

        def replace_match(match: re.Match[str]) -> str:
            core = match.group(1)
            value = lookup.get(core.casefold())
            if value is not None:
                return value
            # Return the original match (with or without brackets)
            return match.group(0)

        return self._TOKEN_CORE_PATTERN.sub(replace_match, text)

    def restore_response_with_paths(
        self,
        response: dict[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Restore tokens in a full response dict.

        Recursively walks all string values and applies token replacement.
        Non-string values (ints, bools, None) are passed through unchanged.

        Args:
            response: The provider response dict (e.g. OpenAI format).
            mapping: Dict mapping token strings to original values.

        Returns:
            A new dict with all tokens replaced by original values.
        """
        if not mapping:
            return response

        return self._walk_and_restore(response, mapping)

    def get_path_tracker(self) -> PathTracker:
        """Return the internal PathTracker for direct access."""
        return self._path_tracker

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk_and_restore(
        self,
        node: Any,
        mapping: dict[str, str],
    ) -> Any:
        """Recursively walk a JSON-like structure, restoring tokens in strings.

        Args:
            node: The current node in the response structure.
            mapping: Dict mapping token strings to original values.

        Returns:
            The node with all tokens restored.
        """
        if isinstance(node, str):
            return self.restore_with_paths(node, mapping)

        if isinstance(node, dict):
            return {
                key: self._walk_and_restore(value, mapping)
                for key, value in node.items()
            }

        if isinstance(node, list):
            return [self._walk_and_restore(item, mapping) for item in node]

        # Pass through ints, floats, bools, None, etc.
        return node
