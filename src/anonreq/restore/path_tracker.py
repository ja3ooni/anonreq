"""PathTracker — records which JSON/dot-notation path each token came from.

This enables path-aware restoration: knowing the exact JSON path where a
token appeared allows precise replacement in structured responses, especially
for tool call arguments, nested content, and multipart parts.
"""

from __future__ import annotations


class PathTracker:
    """Tracks JSON pointer / dot-notation paths for anonymization tokens.

    Usage::

        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        tracker.track("[EMAIL_0]", "messages.1.content")

        paths = tracker.get_path("[EMAIL_0]")
        # → ["messages.0.content", "messages.1.content"]

        all_paths = tracker.get_all()
        # → {"[EMAIL_0]": ["messages.0.content", "messages.1.content"]}
    """

    def __init__(self) -> None:
        self._paths: dict[str, list[str]] = {}

    def track(self, entity_key: str, path: str) -> None:
        """Record that *entity_key* (a token like ``[EMAIL_0]``) appeared at
        the given *path* (dot-notation, e.g. ``messages.0.tool_calls.0.function``).

        If the same (*key*, *path*) pair is added more than once, the path is
        not duplicated.

        Raises:
            TypeError: If *entity_key* or *path* are ``None``.
        """
        if entity_key is None:
            raise TypeError("entity_key must be a string, not None")
        if path is None:
            raise TypeError("path must be a string, not None")

        if entity_key not in self._paths:
            self._paths[entity_key] = []

        existing = self._paths[entity_key]
        if path not in existing:
            existing.append(path)

    def get_path(self, entity_key: str) -> list[str]:
        """Return all tracked paths for *entity_key*.

        Returns an empty list if the key has not been tracked.
        """
        return list(self._paths.get(entity_key, []))

    def get_all(self) -> dict[str, list[str]]:
        """Return the full mapping of entity_key → list of paths."""
        return {k: list(v) for k, v in self._paths.items()}

    def clear(self) -> None:
        """Remove all tracked data."""
        self._paths.clear()
