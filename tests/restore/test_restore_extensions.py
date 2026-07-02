"""Tests for RestoreEngine — path-aware token restoration.

Tests cover:
- Basic path-aware text restoration
- Response dict restoration with path awareness
- Tool call arguments restoration
- Streaming chunk handling
- Edge cases: empty mapping, missing paths, no path tracker
"""

from __future__ import annotations

import pytest

from anonreq.restore.path_tracker import PathTracker
from anonreq.restore.engine import RestoreEngine


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def path_tracker() -> PathTracker:
    """PathTracker with some known paths."""
    tracker = PathTracker()
    tracker.track("[EMAIL_0]", "messages.0.content")
    tracker.track("[PHONE_0]", "messages.1.content")
    tracker.track("[SSN_0]", "messages.0.tool_calls.0.function.arguments")
    return tracker


@pytest.fixture
def engine(path_tracker: PathTracker) -> RestoreEngine:
    """RestoreEngine with a PathTracker."""
    return RestoreEngine(path_tracker=path_tracker)


@pytest.fixture
def engine_no_tracker() -> RestoreEngine:
    """RestoreEngine without explicit PathTracker (auto-created)."""
    return RestoreEngine()


@pytest.fixture
def sample_mapping() -> dict[str, str]:
    return {
        "[EMAIL_0]": "user@example.com",
        "[PHONE_0]": "+1-555-0123",
        "[SSN_0]": "123-45-6789",
        "[NAME_0]": "Alice Smith",
    }


# ── Test RestoreEngine ─────────────────────────────────────────────────────


class TestRestoreEngineInit:
    """Test RestoreEngine initialization."""

    def test_with_explicit_path_tracker(self, path_tracker: PathTracker) -> None:
        engine = RestoreEngine(path_tracker=path_tracker)
        assert engine.path_tracker is path_tracker

    def test_with_auto_path_tracker(self) -> None:
        engine = RestoreEngine()
        assert isinstance(engine.path_tracker, PathTracker)
        assert engine.path_tracker.get_all() == {}

    def test_invalid_path_tracker_type(self) -> None:
        with pytest.raises(TypeError):
            RestoreEngine(path_tracker="not_a_tracker")  # type: ignore[arg-type]


class TestRestoreWithPaths:
    """Tests for restore_with_paths method."""

    def test_basic_text_restoration(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Basic text restoration replaces tokens in plain text."""
        text = "Contact [EMAIL_0] or [PHONE_0]"
        result = engine.restore_with_paths(text, sample_mapping)
        assert "user@example.com" in result
        assert "+1-555-0123" in result
        assert "[EMAIL_0]" not in result
        assert "[PHONE_0]" not in result

    def test_no_mapping(self, engine: RestoreEngine) -> None:
        """Empty mapping returns text unchanged."""
        text = "Hello [EMAIL_0]"
        result = engine.restore_with_paths(text, {})
        assert result == "Hello [EMAIL_0]"

    def test_empty_text(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Empty text returns empty string."""
        result = engine.restore_with_paths("", sample_mapping)
        assert result == ""

    def test_no_tokens_in_text(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Text without tokens is returned unchanged."""
        text = "Just a regular message"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "Just a regular message"

    def test_case_insensitive_matching(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Token matching is case-insensitive per SSE-04."""
        text = "Contact [email_0]"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "Contact user@example.com"

    def test_bracket_optional_matching(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Tokens without brackets are also matched."""
        text = "Contact EMAIL_0"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "Contact user@example.com"

    def test_sorted_by_length(self, engine: RestoreEngine) -> None:
        """Longer tokens replaced first to avoid partial collisions."""
        mapping = {
            "[NAME_10]": "Ten",
            "[NAME_1]": "One",
        }
        text = "[NAME_10] and [NAME_1]"
        result = engine.restore_with_paths(text, mapping)
        assert result == "Ten and One"

    def test_multiple_occurrences(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Same token appearing multiple times is all replaced."""
        text = "[EMAIL_0] and [EMAIL_0] again"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "user@example.com and user@example.com again"

    def test_path_tracker_not_modified(self, engine: RestoreEngine, path_tracker: PathTracker, sample_mapping: dict[str, str]) -> None:
        """restore_with_paths does not modify the path tracker."""
        before = path_tracker.get_all()
        engine.restore_with_paths("Hello [EMAIL_0]", sample_mapping)
        assert path_tracker.get_all() == before

    def test_partial_token_not_replaced(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Partial tokens are not replaced."""
        text = "Contact [EM"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "Contact [EM"

    def test_mixed_tokens_and_text(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Mix of tokens and regular text is handled correctly."""
        text = "Name: [NAME_0], Email: [EMAIL_0]"
        result = engine.restore_with_paths(text, sample_mapping)
        assert result == "Name: Alice Smith, Email: user@example.com"


class TestRestoreResponseWithPaths:
    """Tests for restore_response_with_paths method."""

    def test_restore_simple_response(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Restore tokens in a simple response dict."""
        response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Contact [EMAIL_0] for help"
                    }
                }
            ]
        }
        result = engine.restore_response_with_paths(response, sample_mapping)
        content = result["choices"][0]["message"]["content"]
        assert "user@example.com" in content
        assert "[EMAIL_0]" not in content

    def test_restore_tool_call_arguments(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Restore tokens in tool call arguments using path tracking."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "lookup_user",
                                    "arguments": '{"ssn": "[SSN_0]", "name": "[NAME_0]"}'
                                }
                            }
                        ]
                    }
                }
            ]
        }
        result = engine.restore_response_with_paths(response, sample_mapping)
        args = result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        assert "123-45-6789" in args
        assert "[SSN_0]" not in args

    def test_restore_nested_content(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Restore tokens in nested content structures."""
        response = {
            "data": {
                "users": [
                    {"email": "[EMAIL_0]", "name": "[NAME_0]"}
                ]
            }
        }
        result = engine.restore_response_with_paths(response, sample_mapping)
        assert result["data"]["users"][0]["email"] == "user@example.com"
        assert result["data"]["users"][0]["name"] == "Alice Smith"

    def test_empty_response(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Empty response returns empty dict."""
        result = engine.restore_response_with_paths({}, sample_mapping)
        assert result == {}

    def test_no_mapping(self, engine: RestoreEngine) -> None:
        """No mapping returns response unchanged."""
        response = {"content": "[EMAIL_0]"}
        result = engine.restore_response_with_paths(response, {})
        assert result == {"content": "[EMAIL_0]"}

    def test_response_with_numeric_values(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Numeric values are preserved."""
        response = {"count": 42, "active": True, "content": "[EMAIL_0]"}
        result = engine.restore_response_with_paths(response, sample_mapping)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["content"] == "user@example.com"

    def test_response_with_list_messages(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Restore in a list of messages with path info."""
        response = {
            "choices": [
                {"message": {"content": "[EMAIL_0]"}},
                {"message": {"content": "[PHONE_0]"}},
            ]
        }
        result = engine.restore_response_with_paths(response, sample_mapping)
        assert result["choices"][0]["message"]["content"] == "user@example.com"
        assert result["choices"][1]["message"]["content"] == "+1-555-0123"

    def test_deeply_nested_restoration(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Deeply nested structures are handled."""
        response = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "[EMAIL_0]"
                    }
                }
            }
        }
        result = engine.restore_response_with_paths(response, sample_mapping)
        assert result["level1"]["level2"]["level3"]["value"] == "user@example.com"


class TestStreamingIntegration:
    """Tests for streaming-related restoration features."""

    def test_restore_streaming_chunk(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Restore tokens in a streaming text chunk."""
        chunk = "Hello [EMAIL_0], your"
        result = engine.restore_with_paths(chunk, sample_mapping)
        assert "user@example.com" in result

    def test_restore_chunk_with_partial_token(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Partial token at chunk boundary is preserved for TailBuffer."""
        chunk = "Contact [EM"
        result = engine.restore_with_paths(chunk, sample_mapping)
        # Partial token should not be replaced
        assert result == "Contact [EM"

    def test_restore_completed_token_across_chunks(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """When a token is completed across chunks, it restores correctly."""
        chunk1 = "Contact [EM"
        chunk2 = "AIL_0] for details"

        result1 = engine.restore_with_paths(chunk1, sample_mapping)
        assert result1 == "Contact [EM"  # Partial, left as-is

        # Simulate flush of accumulated buffer
        combined = chunk1 + chunk2
        result2 = engine.restore_with_paths(combined, sample_mapping)
        assert "user@example.com" in result2

    def test_streaming_tool_call_chunk(self, engine: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Tool call arguments in streaming chunks are restored."""
        chunk = '{"ssn": "[SSN_0]"}'
        result = engine.restore_with_paths(chunk, sample_mapping)
        assert "123-45-6789" in result


class TestEngineWithoutTracker:
    """Tests when no explicit PathTracker is provided."""

    def test_works_without_explicit_tracker(self, engine_no_tracker: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Engine works with auto-created empty path tracker."""
        result = engine_no_tracker.restore_with_paths("Hello [EMAIL_0]", sample_mapping)
        assert result == "Hello user@example.com"

    def test_response_restore_without_tracker(self, engine_no_tracker: RestoreEngine, sample_mapping: dict[str, str]) -> None:
        """Response restoration works without explicit path tracker."""
        response = {"content": "[EMAIL_0]"}
        result = engine_no_tracker.restore_response_with_paths(response, sample_mapping)
        assert result["content"] == "user@example.com"


class TestBackslashSafety:
    """Tests for backslash/escape safety in replacement values."""

    def test_backslash_in_value(self, engine: RestoreEngine) -> None:
        """Values containing backslashes are not interpreted as escapes."""
        mapping = {"[PATH_0]": "C:\\Users\\test"}
        text = "Path: [PATH_0]"
        result = engine.restore_with_paths(text, mapping)
        assert result == "Path: C:\\Users\\test"

    def test_number_in_value(self, engine: RestoreEngine) -> None:
        """Values containing numbers are not interpreted as group refs."""
        mapping = {"[NUM_0]": "\\1"}
        text = "Value: [NUM_0]"
        result = engine.restore_with_paths(text, mapping)
        assert result == "Value: \\1"
