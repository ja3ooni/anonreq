"""Tool call argument extraction and PII detection.

Extracts tool call arguments from provider-specific request/response
formats (OpenAI, Anthropic, MCP) and runs them through the JsonAnalyzer
for PII detection.  The detected entities are collected per-tool-call so
the downstream tokenization engine can replace them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from anonreq.multimodal.json_analyzer import JsonAnalyzer

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ToolCallDetection:
    """PII detection result for a single tool call.

    Attributes:
        index: Position of this tool call in the source array.
        tool_call_id: Provider-specific identifier (e.g. ``call_abc``).
        function_name: Name of the function / tool being invoked.
        arguments: Parsed arguments dict (empty dict if unparseable).
        entities: Entities detected by the JsonAnalyzer.
        has_pii: ``True`` when *entities* is non-empty.
    """

    index: int
    tool_call_id: str | None
    function_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    entities: list[dict] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return len(self.entities) > 0


@dataclass
class ToolCallResult:
    """Aggregated PII detection result for a message or payload.

    Attributes:
        provider: Detection provider name (``"openai"``, ``"anthropic"``,
            ``"mcp"``).
        detections: Per-tool-call detection results.
    """

    provider: str
    detections: list[ToolCallDetection] = field(default_factory=list)

    @property
    def total_entities(self) -> int:
        return sum(len(d.entities) for d in self.detections)

    @property
    def has_pii(self) -> bool:
        return any(d.has_pii for d in self.detections)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _analyze_arguments(
    arguments: Any,
    json_analyzer: JsonAnalyzer,
) -> tuple[dict[str, Any] | Any, list[dict]]:
    """Parse *arguments* (a JSON string or dict) and detect PII.

    Returns ``(parsed_value, entities)`` where *parsed_value* is the
    original deserialised value (a dict for JSON objects, a scalar for
    primitive JSON values).  If the value cannot be parsed or is
    ``None``, returns an empty dict and empty list.
    """
    if arguments is None:
        return {}, []

    if isinstance(arguments, str):
        try:
            parsed_val = json.loads(arguments)
        except (json.JSONDecodeError, ValueError):
            return {}, []  # malformed → empty

        # For non-dict top-level values (strings, numbers, etc.) wrap in
        # a temporary dict for analysis but return the original value.
        if not isinstance(parsed_val, dict):
            wrapped = {"_value": parsed_val}
            result = await json_analyzer.analyze(wrapped)
            entities_result = result.entities if hasattr(result, "entities") else []
            return parsed_val, entities_result
    else:
        parsed_val = arguments

    # parsed_val is already a dict (or something that isn't a string)
    result = await json_analyzer.analyze(parsed_val)
    entities_result = result.entities if hasattr(result, "entities") else []
    return parsed_val, entities_result


# ---------------------------------------------------------------------------
# Task 1 — OpenAI tool_calls
# ---------------------------------------------------------------------------


async def extract_tool_calls_openai(
    message: dict[str, Any],
    json_analyzer: JsonAnalyzer,
) -> ToolCallResult:
    """Extract and analyze ``function.arguments`` from an OpenAI tool_calls list.

    *message* should be a dict with an optional ``tool_calls`` key
    (``list[dict]``).  Each entry in the array must have ``id``,
    ``type``, and a ``function`` dict with ``name`` and ``arguments``.

    Returns a :class:`ToolCallResult` with per-tool-call detections.
    """
    result = ToolCallResult(provider="openai")
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return result

    for idx, tc in enumerate(tool_calls):
        func = tc.get("function", {}) or {}
        raw_args = func.get("arguments")
        parsed, entities = await _analyze_arguments(raw_args, json_analyzer)

        result.detections.append(
            ToolCallDetection(
                index=idx,
                tool_call_id=tc.get("id"),
                function_name=func.get("name", ""),
                arguments=parsed,
                entities=entities,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Task 2 — Anthropic tool_use
# ---------------------------------------------------------------------------


async def extract_tool_calls_anthropic(
    content: list[dict[str, Any]],
    json_analyzer: JsonAnalyzer,
) -> ToolCallResult:
    """Extract and analyze ``input`` from Anthropic ``tool_use`` content blocks.

    *content* is the ``content`` array from an Anthropic message.  Blocks
    with ``type == "tool_use"`` have their ``input`` dict analysed for
    PII.  Other block types (``text``, ``image``, ``tool_result``, etc.)
    are skipped.

    Returns a :class:`ToolCallResult` with per-tool-call detections.
    """
    result = ToolCallResult(provider="anthropic")
    if not content:
        return result

    for idx, block in enumerate(content):
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue

        raw_input = block.get("input")
        parsed, entities = await _analyze_arguments(raw_input, json_analyzer)

        result.detections.append(
            ToolCallDetection(
                index=idx,
                tool_call_id=block.get("id"),
                function_name=block.get("name", ""),
                arguments=parsed,
                entities=entities,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Task 3 — MCP
# ---------------------------------------------------------------------------


async def extract_tool_calls_mcp(
    payload: dict[str, Any],
    json_analyzer: JsonAnalyzer,
) -> ToolCallResult:
    """Extract and analyse tool arguments from an MCP JSON-RPC payload.

    Handles both request (``method == "tools/call"`` → ``params.arguments``)
    and response (``result.content``) payloads.

    Returns a :class:`ToolCallResult` with per-tool-call detections.
    """
    result = ToolCallResult(provider="mcp")

    # --- Request path: tools/call ---
    method = payload.get("method")
    if method == "tools/call":
        params = payload.get("params")
        if not params:  # missing or empty params → nothing to extract
            return result
        raw_args = params.get("arguments") if isinstance(params, dict) else None
        parsed, entities = await _analyze_arguments(raw_args, json_analyzer)
        result.detections.append(
            ToolCallDetection(
                index=0,
                tool_call_id=None,
                function_name=params.get("name", "") if isinstance(params, dict) else "",
                arguments=parsed,
                entities=entities,
            )
        )
        return result

    # --- Response path: result.content ---
    rpc_result = payload.get("result")
    if rpc_result is not None:
        content_list = rpc_result.get("content") if isinstance(rpc_result, dict) else None
        if content_list and isinstance(content_list, list):
            for idx, content_item in enumerate(content_list):
                if isinstance(content_item, dict) and "text" in content_item:
                    text_val = content_item["text"]
                    parsed, entities = await _analyze_arguments(
                        json.dumps({"text": text_val}) if isinstance(text_val, str)
                        else text_val,
                        json_analyzer,
                    )
                    result.detections.append(
                        ToolCallDetection(
                            index=idx,
                            tool_call_id=None,
                            function_name="",
                            arguments=parsed,
                            entities=entities,
                        )
                    )

    return result


# ---------------------------------------------------------------------------
# Task 4 — ToolCallExtractor
# ---------------------------------------------------------------------------


class ToolCallExtractor:
    """Auto-detect the provider format and dispatch to the correct extractor.

    Usage::

        extractor = ToolCallExtractor(json_analyzer)

        # Request path
        req_result = await extractor.extract_request(messages)

        # Response path
        resp_result = await extractor.extract_response(response, provider="openai")
    """

    def __init__(self, json_analyzer: JsonAnalyzer) -> None:
        self._json_analyzer = json_analyzer

    # ------------------------------------------------------------------
    # Request extraction
    # ------------------------------------------------------------------

    async def extract_request(
        self,
        messages: list[dict[str, Any]],
    ) -> ToolCallResult:
        """Extract tool calls from *messages*, auto-detecting the provider format.

        Detection priority:

        1. **MCP** — first message has ``"jsonrpc"`` key.
        2. **OpenAI** — any message has a ``"tool_calls"`` key.
        3. **Anthropic** — any assistant message has a ``content`` list
           containing a ``"tool_use"`` block.
        4. Falls back to an empty result.
        """
        if not messages:
            return ToolCallResult(provider="unknown")

        # 1) MCP detection — jsonrpc at top level
        if isinstance(messages[0], dict) and "jsonrpc" in messages[0]:
            return await extract_tool_calls_mcp(messages[0], self._json_analyzer)

        # 2) OpenAI detection — tool_calls key on any message
        for msg in messages:
            if isinstance(msg, dict) and msg.get("tool_calls"):
                return await extract_tool_calls_openai(msg, self._json_analyzer)

        # 3) Anthropic detection — assistant message with content array
        #    containing a tool_use block
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return await extract_tool_calls_anthropic(
                        content, self._json_analyzer
                    )

        return ToolCallResult(provider="unknown")

    # ------------------------------------------------------------------
    # Response extraction
    # ------------------------------------------------------------------

    async def extract_response(
        self,
        response: dict[str, Any],
        provider: str,
    ) -> ToolCallResult:
        """Extract tool calls from a provider response.

        *response* is the full response dict.  *provider* must be one of
        ``"openai"``, ``"anthropic"``, or ``"mcp"``.
        """
        if provider == "openai":
            choices = response.get("choices", [])
            for choice in choices:
                message = choice.get("message", {}) if isinstance(choice, dict) else {}
                if isinstance(message, dict) and message.get("tool_calls"):
                    return await extract_tool_calls_openai(
                        message, self._json_analyzer
                    )
            return ToolCallResult(provider="openai")

        if provider == "anthropic":
            content = response.get("content", [])
            if isinstance(content, list):
                return await extract_tool_calls_anthropic(
                    content, self._json_analyzer
                )
            return ToolCallResult(provider="anthropic")

        if provider == "mcp":
            return await extract_tool_calls_mcp(response, self._json_analyzer)

        return ToolCallResult(provider=provider)
