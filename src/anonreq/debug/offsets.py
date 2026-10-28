"""Code-point and UTF-16 offsets for anonymization preview entities.

Offsets are 0-based. ``start``/``end`` count Unicode code points (Python
``str`` indexes). ``*_utf16`` counts UTF-16 code units, which is what
browser ``String`` indexes use. Token offsets are into the anonymized
text, not the original.
"""

from __future__ import annotations

import re
from typing import Any

_MESSAGE_INDEX = re.compile(r"^messages\[(\d+)\]")


def utf16_len(text: str) -> int:
    """Number of UTF-16 code units in ``text``."""
    return len(text.encode("utf-16-le")) // 2


def message_index_from_path(path: str) -> int | None:
    match = _MESSAGE_INDEX.match(path)
    if match is None:
        return None
    return int(match.group(1))


def entities_for_text(
    original: str,
    anonymized: str,
    detections: list[dict[str, Any]],
    value_to_token: dict[str, str],
    message_index: int | None,
) -> list[dict[str, Any]]:
    """Build entity records for one text node.

    ``value_to_token`` is the tokenizer's value map (original span text
    to ``[TYPE_N]``). Overlapping spans keep the earliest start.
    """
    spans: list[tuple[int, int, dict[str, Any], str, str]] = []
    for detection in detections:
        try:
            start = int(detection["start"])
            end = int(detection["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start < 0 or end <= start or end > len(original):
            continue
        span = original[start:end]
        token = value_to_token.get(span)
        if not token:
            continue
        spans.append((start, end, detection, span, token))

    spans.sort(key=lambda item: (item[0], item[1]))
    filtered: list[tuple[int, int, dict[str, Any], str, str]] = []
    last_end = -1
    for item in spans:
        if item[0] < last_end:
            continue
        filtered.append(item)
        last_end = item[1]

    cursor = 0
    previous_end = 0
    entities: list[dict[str, Any]] = []
    for start, end, detection, span, token in filtered:
        cursor += start - previous_end
        token_start = cursor
        token_end = token_start + len(token)
        cursor = token_end
        previous_end = end
        try:
            score = float(detection.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        entities.append(
            {
                "entity_type": str(detection.get("entity_type", "UNKNOWN")),
                "span": span,
                "token": token,
                "score": score,
                "start": start,
                "end": end,
                "start_utf16": utf16_len(original[:start]),
                "end_utf16": utf16_len(original[:end]),
                "token_start": token_start,
                "token_end": token_end,
                "token_start_utf16": utf16_len(anonymized[:token_start]),
                "token_end_utf16": utf16_len(anonymized[:token_end]),
                "message_index": message_index,
            }
        )
    return entities


def entities_from_context(
    text_nodes: list[dict[str, Any]] | None,
    detections: list[dict[str, Any]] | None,
    transformed_messages: list[Any],
    value_to_token: dict[str, str],
    *,
    include_message_index: bool,
) -> list[dict[str, Any]]:
    """Project pipeline detections onto preview entity records."""
    by_node: dict[int, list[dict[str, Any]]] = {}
    for detection in detections or []:
        index = detection.get("node_index", 0)
        try:
            node_index = int(index)
        except (TypeError, ValueError):
            node_index = 0
        by_node.setdefault(node_index, []).append(detection)

    entities: list[dict[str, Any]] = []
    for index, node in enumerate(text_nodes or []):
        original = str(node.get("value", ""))
        path = str(node.get("path", ""))
        message_index = message_index_from_path(path)
        anonymized = original
        if (
            message_index is not None
            and path.endswith(".content")
            and message_index < len(transformed_messages)
            and isinstance(transformed_messages[message_index], dict)
        ):
            content = transformed_messages[message_index].get("content")
            if isinstance(content, str):
                anonymized = content
        entities.extend(
            entities_for_text(
                original,
                anonymized,
                by_node.get(index, []),
                value_to_token,
                message_index if include_message_index else None,
            )
        )
    return entities
