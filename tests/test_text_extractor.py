"""Tests for TextExtractor — recursive JSON walker from OpenAI chat payloads.

Per D-29, D-30, D-31:
- TextExtractor walks messages[] by index
- Extracts string content and tool_calls arguments
- Skips non-string content (multimodal lists, None)
- Returns TextNode dicts with path, role, value
"""

from __future__ import annotations

import pytest

from anonreq.pipeline.extraction import TextExtractor


class TestTextExtractor:
    """Test suite for TextExtractor."""

    def test_extract_single_user_message(self):
        """Extract text from a single user message."""
        body = {"messages": [{"role": "user", "content": "Hello, world!"}]}
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 1
        assert nodes[0]["path"] == "messages[0].content"
        assert nodes[0]["role"] == "user"
        assert nodes[0]["value"] == "Hello, world!"

    def test_extract_all_roles(self):
        """Extract text from all message roles (system, user, assistant, tool, function)."""
        body = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Tell me a joke."},
                {"role": "assistant", "content": "Why did the chicken cross the road?"},
                {"role": "tool", "content": "Function returned: 42"},
                {"role": "function", "content": "Function result: success"},
            ]
        }
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 5
        assert nodes[0]["role"] == "system"
        assert nodes[1]["role"] == "user"
        assert nodes[2]["role"] == "assistant"
        assert nodes[3]["role"] == "tool"
        assert nodes[4]["role"] == "function"

    def test_extract_skips_non_string_content(self):
        """Skip content that is None or a list (multimodal content)."""
        body = {
            "messages": [
                {"role": "user", "content": None},
                {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
                {"role": "user", "content": "valid text"},
            ]
        }
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 1
        assert nodes[0]["value"] == "valid text"

    def test_extract_skips_empty_string_content(self):
        """Skip content that is an empty or whitespace-only string."""
        body = {
            "messages": [
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "   "},
                {"role": "user", "content": "actual content"},
            ]
        }
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 1
        assert nodes[0]["value"] == "actual content"

    def test_extract_tool_calls_arguments(self):
        """Extract text from tool_calls[].function.arguments."""
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Let me look that up.",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_database",
                                "arguments": '{"query": "user email"}',
                            }
                        }
                    ],
                }
            ]
        }
        nodes = TextExtractor.extract(body)
        # Should have 2 nodes: content + tool_calls[0].function.arguments
        assert len(nodes) == 2
        assert nodes[0]["path"] == "messages[0].content"
        assert nodes[0]["value"] == "Let me look that up."
        assert nodes[1]["path"] == "messages[0].tool_calls[0].function.arguments"
        assert nodes[1]["value"] == '{"query": "user email"}'

    def test_extract_multiple_tool_calls(self):
        """Extract arguments from multiple tool_calls."""
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"function": {"name": "fn1", "arguments": '{"a": 1}'}},
                        {"function": {"name": "fn2", "arguments": '{"b": 2}'}},
                    ],
                }
            ]
        }
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 2
        assert nodes[0]["path"] == "messages[0].tool_calls[0].function.arguments"
        assert nodes[0]["value"] == '{"a": 1}'
        assert nodes[1]["path"] == "messages[0].tool_calls[1].function.arguments"
        assert nodes[1]["value"] == '{"b": 2}'

    def test_empty_messages_returns_empty_list(self):
        """Empty messages array produces empty list."""
        body = {"messages": []}
        nodes = TextExtractor.extract(body)
        assert nodes == []

    def test_missing_messages_returns_empty_list(self):
        """Missing messages key produces empty list."""
        body = {}
        nodes = TextExtractor.extract(body)
        assert nodes == []

    def test_path_notation_correctness(self):
        """Path notation uses bracket indices correctly."""
        body = {
            "messages": [
                {"role": "system", "content": "sys msg"},
                {"role": "user", "content": "user msg"},
                {"role": "assistant", "content": "assistant msg"},
            ]
        }
        nodes = TextExtractor.extract(body)
        assert nodes[0]["path"] == "messages[0].content"
        assert nodes[1]["path"] == "messages[1].content"
        assert nodes[2]["path"] == "messages[2].content"

    def test_content_is_not_string_skipped(self):
        """Non-string, non-None content types (int, dict, etc.) are skipped."""
        body = {
            "messages": [
                {"role": "user", "content": 123},
                {"role": "user", "content": {"nested": "object"}},
                {"role": "user", "content": True},
                {"role": "user", "content": "valid string"},
            ]
        }
        nodes = TextExtractor.extract(body)
        assert len(nodes) == 1
        assert nodes[0]["value"] == "valid string"

    def test_multiple_text_nodes_ordered_by_message_index(self):
        """Text nodes are returned in message index order."""
        body = {
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "second", "tool_calls": [{"function": {"name": "f", "arguments": '{"x": 1}'}}]},
                {"role": "user", "content": "third"},
            ]
        }
        nodes = TextExtractor.extract(body)
        # Order: messages[0].content, messages[1].content, messages[1].tool_calls[0].arguments, messages[2].content
        assert len(nodes) == 4
        assert nodes[0]["value"] == "first"
        assert nodes[1]["value"] == "second"
        assert nodes[2]["value"] == '{"x": 1}'
        assert nodes[3]["value"] == "third"
