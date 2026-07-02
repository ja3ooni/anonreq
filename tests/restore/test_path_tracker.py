"""Tests for PathTracker — path-aware token tracking.

Follows TDD: test first, implement second.
Covers track, get_path, get_all, clear, and edge cases.
"""

from __future__ import annotations

import pytest

from anonreq.restore.path_tracker import PathTracker


class TestPathTracker:
    """Test suite for PathTracker."""

    def test_track_single_path(self) -> None:
        """Track a single entity key with one path."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        assert tracker.get_path("[EMAIL_0]") == ["messages.0.content"]

    def test_track_multiple_paths(self) -> None:
        """Track an entity key appearing at multiple paths."""
        tracker = PathTracker()
        tracker.track("[PHONE_0]", "messages.0.content")
        tracker.track("[PHONE_0]", "messages.1.content")
        assert tracker.get_path("[PHONE_0]") == [
            "messages.0.content",
            "messages.1.content",
        ]

    def test_track_duplicate_path_ignored(self) -> None:
        """Adding the same path for the same key should not duplicate it."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        tracker.track("[EMAIL_0]", "messages.0.content")
        assert tracker.get_path("[EMAIL_0]") == ["messages.0.content"]

    def test_get_path_missing_key(self) -> None:
        """Getting path for a non-existent key returns empty list."""
        tracker = PathTracker()
        assert tracker.get_path("[NONEXISTENT_0]") == []

    def test_get_all_empty(self) -> None:
        """Getting all when nothing tracked returns empty dict."""
        tracker = PathTracker()
        assert tracker.get_all() == {}

    def test_get_all_with_data(self) -> None:
        """Getting all returns full mapping of entity_key -> paths."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        tracker.track("[PHONE_0]", "messages.1.tool_calls.0.arguments")
        all_data = tracker.get_all()
        assert "[EMAIL_0]" in all_data
        assert "[PHONE_0]" in all_data
        assert all_data["[EMAIL_0]"] == ["messages.0.content"]
        assert all_data["[PHONE_0]"] == ["messages.1.tool_calls.0.arguments"]

    def test_clear(self) -> None:
        """Clear removes all tracked data."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        tracker.clear()
        assert tracker.get_all() == {}
        assert tracker.get_path("[EMAIL_0]") == []

    def test_track_empty_key(self) -> None:
        """Tracking with an empty entity key should not raise an error."""
        tracker = PathTracker()
        tracker.track("", "messages.0.content")
        assert tracker.get_path("") == ["messages.0.content"]

    def test_track_empty_path(self) -> None:
        """Tracking with an empty path should store the empty path."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "")
        assert tracker.get_path("[EMAIL_0]") == [""]

    def test_track_none_key(self) -> None:
        """Tracking with None key should raise TypeError."""
        tracker = PathTracker()
        with pytest.raises(TypeError):
            tracker.track(None, "messages.0.content")  # type: ignore[arg-type]

    def test_track_none_path(self) -> None:
        """Tracking with None path should raise TypeError."""
        tracker = PathTracker()
        with pytest.raises(TypeError):
            tracker.track("[EMAIL_0]", None)  # type: ignore[arg-type]

    def test_multiple_entity_keys(self) -> None:
        """Multiple different entity keys are tracked independently."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "a")
        tracker.track("[PHONE_0]", "b")
        tracker.track("[EMAIL_1]", "c")
        assert tracker.get_path("[EMAIL_0]") == ["a"]
        assert tracker.get_path("[PHONE_0]") == ["b"]
        assert tracker.get_path("[EMAIL_1]") == ["c"]

    def test_dot_notation_path_format(self) -> None:
        """Paths use dot-notation format with array indices."""
        tracker = PathTracker()
        path = "messages.0.tool_calls.0.function.arguments"
        tracker.track("[SSN_0]", path)
        assert tracker.get_path("[SSN_0]") == [path]

    def test_clear_after_track(self) -> None:
        """Tracking after clear works correctly."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0")
        tracker.clear()
        tracker.track("[EMAIL_0]", "messages.1")
        assert tracker.get_path("[EMAIL_0]") == ["messages.1"]

    def test_is_empty_initially(self) -> None:
        """New PathTracker is empty."""
        tracker = PathTracker()
        assert tracker.get_all() == {}
