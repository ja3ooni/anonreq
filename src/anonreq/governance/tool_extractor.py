"""Multi-format tool call and tool result extraction.

Supports 3 formats per D-009:
- OpenAI: tool_calls in assistant messages
- Anthropic: tool_use content blocks
- MCP: JSON-RPC tools/call method

Per D-010: tool parameters are extracted for downstream anonymization.
Per D-018, D-019, D-020: domain detection (model vs host) for strict isolation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class ToolExtractionError(Exception):
    """Raised when tool data cannot be extracted from a message.

    Consistent with fail-secure principles — malformed tool data
    triggers an extraction error which prevents forwarding.
    """


@dataclass
class ToolCall:
    """A tool call extracted from a request message.

    Attributes:
        id: Unique identifier for this tool call.
        name: Name of the tool being called.
        arguments: Parsed arguments dict.
        format: Source format: "openai", "anthropic", or "mcp".
        domain: Tool domain: "model" or "host".
        provider: Provider identifier (optional).
        raw: Original message dict for reconstruction.
    """

    id: str
    name: str
    arguments: dict[str, Any]
    format: str
    domain: str = "model"
    provider: str | None = None
    raw: dict[str, Any] | None = None
    credential_context: str | None = None


@dataclass
class ToolResult:
    """A tool result extracted from a response message.

    Attributes:
        id: ID matching the original tool call.
        name: Name of the tool that produced this result.
        content: Result content (string, dict, or None).
        format: Source format.
        domain: Tool domain.
        is_error: Whether this result represents an error.
    """

    id: str
    name: str = ""
    content: str | dict[str, Any] | None = None
    format: str = ""
    domain: str = "model"
    is_error: bool = False


class ToolExtractor:
    """Extracts tool calls and results from OpenAI, Anthropic, and MCP formats.

    The extractor is stateless — no dependencies on other modules.
    """

    def extract_calls(
        self,
        message: dict[str, Any],
        format: str,
    ) -> list[ToolCall]:
        """Extract tool calls from a message in the given format.

        Args:
            message: Message dict from the request body.
            format: One of "openai", "anthropic", or "mcp".

        Returns:
            List of ToolCall objects extracted from the message.

        Raises:
            ToolExtractionError: If tool data is malformed.
        """
        if format == "openai":
            return self._extract_openai_calls(message)
        elif format == "anthropic":
            return self._extract_anthropic_calls(message)
        elif format == "mcp":
            return self._extract_mcp_calls(message)
        return []

    def extract_results(
        self,
        message: dict[str, Any],
        format: str,
    ) -> list[ToolResult]:
        """Extract tool results from a message in the given format.

        Args:
            message: Message dict from the response body.
            format: One of "openai", "anthropic", or "mcp".

        Returns:
            List of ToolResult objects extracted from the message.
        """
        if format == "openai":
            return self._extract_openai_results(message)
        elif format == "anthropic":
            return self._extract_anthropic_results(message)
        elif format == "mcp":
            return self._extract_mcp_results(message)
        return []

    def detect_format(
        self,
        request_body: dict[str, Any],
        _headers: dict[str, str],
    ) -> str | None:
        """Auto-detect which tool format is in use based on the request body.

        Detection heuristics:
        - If ``messages[].tool_calls`` exists → openai
        - If ``messages[].content[].type == 'tool_use'`` → anthropic
        - If ``method == 'tools/call'`` → mcp

        Args:
            request_body: The full request body dict.
            headers: Request headers dict.

        Returns:
            Format string ("openai", "anthropic", "mcp") or None if unknown.
        """
        # MCP: check method field first (most specific signal)
        if isinstance(request_body.get("method"), str):
            method: str = request_body["method"]
            if method == "tools/call" or method.startswith("tools/"):
                return "mcp"

        # OpenAI/Anthropic: check messages array
        messages = request_body.get("messages")
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                # OpenAI: tool_calls field
                if "tool_calls" in msg:
                    return "openai"

                # Anthropic: content blocks with type=tool_use
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            return "anthropic"

        return None

    def detect_domain(
        self,
        headers: dict[str, str],
        _request_body: dict[str, Any],
    ) -> str:
        """Detect tool domain based on headers.

        Domain detection logic:
        - If ``X-AnonReq-Tool-Domain: host`` header → "host"
        - Otherwise → "model"

        Args:
            headers: Request headers dict.
            request_body: The full request body (unused, for future extensibility).

        Returns:
            "host" or "model".
        """
        # Header-based domain detection
        domain_header = headers.get("X-AnonReq-Tool-Domain", "").strip().lower()
        if domain_header == "host":
            return "host"
        return "model"

    def _extract_openai_calls(
        self,
        message: dict[str, Any],
    ) -> list[ToolCall]:
        """Extract tool calls from OpenAI format (tool_calls array)."""
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            return []

        result: list[ToolCall] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue

            call_id = tc.get("id", "")

            func = tc.get("function", {})
            if not isinstance(func, dict):
                continue

            name = func.get("name", "")
            if not name or not isinstance(name, str):
                raise ToolExtractionError(
                    f"OpenAI tool call '{call_id}': missing or invalid 'name' in function"
                )

            args_raw = func.get("arguments", "{}")
            if isinstance(args_raw, str):
                try:
                    arguments = json.loads(args_raw)
                except json.JSONDecodeError as exc:
                    raise ToolExtractionError(  # noqa: B904
                        f"OpenAI tool call '{call_id}': invalid JSON in arguments: {exc}"
                    )
            elif isinstance(args_raw, dict):
                arguments = args_raw
            else:
                arguments = {}

            result.append(ToolCall(
                id=call_id,
                name=name,
                arguments=arguments,
                format="openai",
                raw=tc,
            ))

        return result

    def _extract_anthropic_calls(
        self,
        message: dict[str, Any],
    ) -> list[ToolCall]:
        """Extract tool calls from Anthropic format (tool_use content blocks)."""
        content = message.get("content")
        if not isinstance(content, list):
            return []

        result: list[ToolCall] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue

            call_id = block.get("id", "")
            name = block.get("name", "")
            if not name or not isinstance(name, str):
                raise ToolExtractionError(
                    f"Anthropic tool_use '{call_id}': missing or invalid 'name'"
                )

            input_data = block.get("input", {})
            if not isinstance(input_data, dict):
                input_data = {}

            result.append(ToolCall(
                id=call_id,
                name=name,
                arguments=input_data,
                format="anthropic",
                raw=block,
            ))

        return result

    def _extract_mcp_calls(
        self,
        message: dict[str, Any],
    ) -> list[ToolCall]:
        """Extract tool calls from MCP format (JSON-RPC tools/call method).

        Per D-009: supports MCP protocol tools/call method.
        """
        method = message.get("method", "")
        if method != "tools/call":
            return []

        call_id = str(message.get("id", ""))
        params = message.get("params", {})
        if not isinstance(params, dict):
            params = {}

        name = params.get("name", "")
        if not name or not isinstance(name, str):
            raise ToolExtractionError(
                f"MCP tools/call '{call_id}': missing or invalid 'name' in params"
            )

        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}

        return [ToolCall(
            id=call_id,
            name=name,
            arguments=arguments,
            format="mcp",
            raw=message,
        )]

    def _extract_openai_results(
        self,
        message: dict[str, Any],
    ) -> list[ToolResult]:
        """Extract tool results from OpenAI format (tool role messages)."""
        role = message.get("role", "")
        if role != "tool":
            return []

        call_id = message.get("tool_call_id", "")
        content = message.get("content")

        # Extract tool name from name field if present, or default to call_id
        name = message.get("name", "") or ""

        return [ToolResult(
            id=call_id,
            name=name,
            content=content,
            format="openai",
            is_error=False,
        )]

    def _extract_anthropic_results(
        self,
        message: dict[str, Any],
    ) -> list[ToolResult]:
        """Extract tool results from Anthropic format (tool_result content blocks)."""
        content = message.get("content")
        if not isinstance(content, list):
            return []

        result: list[ToolResult] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue

            call_id = block.get("tool_use_id", "")
            block_content = block.get("content", "")
            is_error = bool(block.get("is_error", False))

            result.append(ToolResult(
                id=call_id,
                content=block_content,
                format="anthropic",
                is_error=is_error,
            ))

        return result

    def _extract_mcp_results(
        self,
        message: dict[str, Any],
    ) -> list[ToolResult]:
        """Extract tool results from MCP JSON-RPC response format.

        Supports both success (result field) and error responses.
        """
        call_id = str(message.get("id", ""))

        # Error response
        if "error" in message:
            error = message.get("error", {})
            return [ToolResult(
                id=call_id,
                content=error,
                format="mcp",
                is_error=True,
            )]

        # Success response
        if "result" in message:
            result_data = message.get("result", {})
            return [ToolResult(
                id=call_id,
                content=result_data,
                format="mcp",
                is_error=False,
            )]

        return []
