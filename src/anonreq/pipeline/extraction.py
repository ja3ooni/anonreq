"""TextExtractor — recursive JSON walker from OpenAI chat payloads.

Per D-29, D-30, D-31:
- Walks ``messages[]`` list by index
- Extracts string ``content`` for all roles (system, user, assistant, tool, function)
- Extracts ``tool_calls[].function.arguments`` as ``TextNode`` entries
- Skips non-string content (multimodal lists, ``None``, empty strings)
- Returns ``TextNode`` dicts with ``path``, ``role``, ``value`` keys

Path notation uses bracket indices (e.g. ``messages[0].content``) for
traceability.
"""

from __future__ import annotations

from typing import Any


class TextExtractor:
    """Recursive JSON walker extracting TextNodes from OpenAI chat payloads.

    Usage::

        nodes = TextExtractor.extract(request_body)
        # Returns: [{"path": "messages[0].content", "role": "user", "value": "..."}, ...]
    """

    @staticmethod
    def extract(body: dict[str, Any]) -> list[dict[str, str]]:
        """Extract TextNodes from an OpenAI chat request body.

        Walks ``body["messages"]`` by index and extracts:
        - ``content`` if it is a non-empty string
        - ``tool_calls[].function.arguments`` if present and a string

        Args:
            body: Parsed OpenAI chat request dictionary.

        Returns:
            List of dicts with ``path``, ``role``, ``value`` keys, in message
            index order.
        """
        nodes: list[dict[str, str]] = []
        messages = body.get("messages", [])
        if not isinstance(messages, list):
            return nodes

        for idx, message in enumerate(messages):
            if not isinstance(message, dict):
                continue

            role = message.get("role", "unknown")

            # Extract content if it is a non-empty string
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                nodes.append(
                    {
                        "path": f"messages[{idx}].content",
                        "role": role,
                        "value": content,
                    }
                )

            # Extract tool_calls arguments
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc_idx, tc in enumerate(tool_calls):
                    if not isinstance(tc, dict):
                        continue
                    function = tc.get("function")
                    if isinstance(function, dict):
                        arguments = function.get("arguments")
                        if isinstance(arguments, str) and arguments.strip():
                            nodes.append(
                                {
                                    "path": (
                                        f"messages[{idx}].tool_calls[{tc_idx}]"
                                        ".function.arguments"
                                    ),
                                    "role": role,
                                    "value": arguments,
                                }
                            )

        return nodes
