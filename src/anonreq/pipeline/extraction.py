"""TextExtractor — recursive JSON walker from OpenAI chat payloads.

Per D-29, D-30, D-31:
- Walks ``messages[]`` list by index
- Extracts string ``content`` for all roles (system, user, assistant, tool, function)
- Extracts ``tool_calls[].function.arguments`` as ``TextNode`` entries
- Extracts every text part of multipart/list content, message ``name``,
  the top-level ``user`` field and tool/function descriptions (including
  JSON-schema parameter descriptions)
- Skips non-text parts (images, audio), ``None`` and empty strings
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

        def add(path: str, role: str, value: Any) -> None:
            if isinstance(value, str) and value.strip():
                nodes.append({"path": path, "role": role, "value": value})

        messages = body.get("messages", [])
        if isinstance(messages, list):
            for idx, message in enumerate(messages):
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role", "unknown"))
                base = f"messages[{idx}]"

                content = message.get("content")
                if isinstance(content, str):
                    add(f"{base}.content", role, content)
                elif isinstance(content, list):
                    # Multipart content: every text part is scanned.
                    for part_idx, part in enumerate(content):
                        if isinstance(part, str):
                            add(f"{base}.content[{part_idx}]", role, part)
                        elif isinstance(part, dict):
                            for key in _TEXT_PART_KEYS:
                                add(f"{base}.content[{part_idx}].{key}", role, part.get(key))

                add(f"{base}.name", role, message.get("name"))

                tool_calls = message.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tc_idx, tc in enumerate(tool_calls):
                        if not isinstance(tc, dict):
                            continue
                        function = tc.get("function")
                        if isinstance(function, dict):
                            add(
                                f"{base}.tool_calls[{tc_idx}].function.arguments",
                                role,
                                function.get("arguments"),
                            )

                function_call = message.get("function_call")
                if isinstance(function_call, dict):
                    add(f"{base}.function_call.arguments", role, function_call.get("arguments"))

        add("user", "request", body.get("user"))

        # Tool / function definitions: descriptions are free text that
        # clients sometimes fill with customer data.
        for list_key in ("tools", "functions"):
            definitions = body.get(list_key)
            if not isinstance(definitions, list):
                continue
            for def_idx, definition in enumerate(definitions):
                if not isinstance(definition, dict):
                    continue
                function = definition
                prefix = f"{list_key}[{def_idx}]"
                if list_key == "tools" and "function" in definition:
                    function = definition["function"]
                    prefix += ".function"
                if not isinstance(function, dict):
                    continue
                add(f"{prefix}.description", "tool_definition", function.get("description"))
                _walk_schema_descriptions(function.get("parameters"), f"{prefix}.parameters", add)

        return nodes


# Keys of a content part that carry free text (OpenAI chat and responses
# style parts). Image/audio parts carry no text and are skipped.
_TEXT_PART_KEYS = ("text", "input_text", "refusal")


def _safe_key(key: Any) -> bool:
    """Path segments must be writable back: no dots or brackets."""
    return isinstance(key, str) and key != "" and not any(c in key for c in ".[]")


def _walk_schema_descriptions(schema: Any, path: str, add: Any, depth: int = 0) -> None:
    """Collect ``description`` strings inside a JSON schema."""
    if depth > 12 or not isinstance(schema, dict):
        return
    add(f"{path}.description", "tool_definition", schema.get("description"))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, sub in properties.items():
            if _safe_key(name):
                _walk_schema_descriptions(sub, f"{path}.properties.{name}", add, depth + 1)
    items = schema.get("items")
    if isinstance(items, dict):
        _walk_schema_descriptions(items, f"{path}.items", add, depth + 1)
    for combo in ("anyOf", "oneOf", "allOf"):
        options = schema.get(combo)
        if isinstance(options, list):
            for opt_idx, option in enumerate(options):
                _walk_schema_descriptions(option, f"{path}.{combo}[{opt_idx}]", add, depth + 1)
