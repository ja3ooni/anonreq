"""MCP (Model Context Protocol) JSON-RPC 2.0 message parser.

Provides:
- ``MCPMessage`` — Pydantic model for JSON-RPC 2.0 messages.
- ``MCPToolCall`` — dataclass representing a tool call request.
- ``MCPToolResult`` — dataclass representing a tool call result.
- ``MCPParser`` — parses raw JSON-RPC 2.0 bytes/strings and extracts
  tool calls and results.
- ``MCPParseError`` — raised when a message cannot be parsed.

Per D-007, D-008:
- Supports single messages and batch (list) messages.
- Validates JSON-RPC 2.0 structure.
- ``is_mcp_message()`` heuristic for pre-parse detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class MCPParseError(Exception):
    """Raised when an MCP message cannot be parsed."""


class MCPMessage(BaseModel):
    """A single MCP JSON-RPC 2.0 message.

    Attributes:
        jsonrpc: The JSON-RPC version (always ``"2.0"``).
        id: The request/response ID.
        method: The method name (present in requests, absent in responses).
        params: The method parameters (present in requests).
        result: The result data (present in responses).
    """

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


@dataclass
class MCPToolCall:
    """A tool call extracted from an MCP message.

    Attributes:
        name: The name of the tool being called.
        arguments: The tool call arguments.
        id: The tool call identifier.
        domain: The domain of the tool call (always ``"model"`` for
            model-initiated tool calls, ``"host"`` for host-initiated).
    """

    name: str
    arguments: dict[str, Any]
    id: str
    domain: str = "model"


@dataclass
class MCPToolResult:
    """A tool result extracted from an MCP message.

    Attributes:
        id: The tool call identifier this result corresponds to.
        name: The name of the tool.
        content: The tool result content (string or dict).
        is_error: Whether the tool call resulted in an error.
    """

    id: str
    name: str
    content: str | dict[str, Any]
    is_error: bool = False


class MCPParser:
    """Parses MCP JSON-RPC 2.0 messages and extracts tool calls and results.

    Usage:
        parser = MCPParser()
        message = parser.parse(raw_data)
        tool_calls = parser.extract_tool_calls(message)
        tool_results = parser.extract_tool_results(message)
    """

    def parse(self, raw: bytes | str) -> MCPMessage | list[MCPMessage]:
        """Parse raw MCP message data.

        Accepts both single messages and batch (list) messages.
        Performs basic JSON-RPC 2.0 validation.

        Args:
            raw: Raw bytes or string containing JSON-RPC 2.0 data.

        Returns:
            A single ``MCPMessage`` or a list of ``MCPMessage`` instances.

        Raises:
            MCPParseError: If the data cannot be parsed or validated.
        """
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MCPParseError(f"Invalid JSON: {exc}") from exc

        if isinstance(data, list):
            messages = []
            for item in data:
                messages.append(self._parse_single(item))
            return messages

        if isinstance(data, dict):
            return self._parse_single(data)

        raise MCPParseError(
            f"Expected JSON object or array, got {type(data).__name__}"
        )

    def _parse_single(self, data: dict[str, Any]) -> MCPMessage:
        """Parse a single JSON-RPC 2.0 message dict.

        Args:
            data: A dict representing a single JSON-RPC 2.0 message.

        Returns:
            An ``MCPMessage`` instance.

        Raises:
            MCPParseError: If the message is not valid JSON-RPC 2.0.
        """
        jsonrpc = data.get("jsonrpc")
        if jsonrpc != "2.0":
            raise MCPParseError(
                f"Invalid jsonrpc version: {jsonrpc!r}. Expected '2.0'"
            )

        return MCPMessage(
            jsonrpc=jsonrpc,
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
        )

    def extract_tool_calls(
        self, message: MCPMessage | list[MCPMessage],
    ) -> list[MCPToolCall]:
        """Extract tool calls from an MCP message.

        Handles:
        - ``tools/call`` method requests.
        - ``sampling/createMessage`` responses (host-to-model tool calls).
        - Notifications with tool call content.

        Args:
            message: The parsed MCP message(s).

        Returns:
            A list of ``MCPToolCall`` instances.
        """
        messages = message if isinstance(message, list) else [message]
        tool_calls: list[MCPToolCall] = []

        for msg in messages:
            if msg.method == "tools/call" and msg.params:
                params = msg.params
                tool_calls.append(
                    MCPToolCall(
                        name=params.get("name", "unknown"),
                        arguments=params.get("arguments", {}),
                        id=str(msg.id) if msg.id is not None else "unknown",
                        domain="model",
                    )
                )

            # Handle sampling/createMessage responses
            if msg.result and "tool_calls" in msg.result:
                for tc in msg.result["tool_calls"]:
                    tool_calls.append(
                        MCPToolCall(
                            name=tc.get("name", "unknown"),
                            arguments=tc.get("arguments", {}),
                            id=str(tc.get("id", "unknown")),
                            domain="host",
                        )
                    )

            # Handle notifications with embedded tool calls
            if msg.method and msg.method.startswith("notifications/"):
                if msg.params and "tool_calls" in msg.params:
                    for tc in msg.params["tool_calls"]:
                        tool_calls.append(
                            MCPToolCall(
                                name=tc.get("name", "unknown"),
                                arguments=tc.get("arguments", {}),
                                id=str(tc.get("id", "unknown")),
                                domain="model",
                            )
                        )

        return tool_calls

    def extract_tool_results(
        self, message: MCPMessage | list[MCPMessage],
    ) -> list[MCPToolResult]:
        """Extract tool results from an MCP message.

        Handles:
        - ``tools/call`` response messages (result contains tool output).
        - ``sampling/createMessage`` responses with tool results.

        Args:
            message: The parsed MCP message(s).

        Returns:
            A list of ``MCPToolResult`` instances.
        """
        messages = message if isinstance(message, list) else [message]
        tool_results: list[MCPToolResult] = []

        for msg in messages:
            # tools/call response — result contains tool output
            if msg.result and msg.id is not None:
                result = msg.result
                tool_results.append(
                    MCPToolResult(
                        id=str(msg.id),
                        name=result.get("name", "unknown"),
                        content=result.get("content", {}),
                        is_error=result.get("isError", False),
                    )
                )

            # sampling/createMessage result with tool calls (host-side)
            if msg.result and "model" in msg.result:
                model_result = msg.result["model"]
                if isinstance(model_result, dict) and "tool_calls" in model_result:
                    for tc in model_result["tool_calls"]:
                        tool_results.append(
                            MCPToolResult(
                                id=str(tc.get("id", "unknown")),
                                name=tc.get("name", "unknown"),
                                content=tc.get("content", ""),
                                is_error=False,
                            )
                        )

        return tool_results

    def serialize(self, message: MCPMessage) -> str:
        """Serialize an MCP message back to JSON-RPC 2.0.

        Args:
            message: The ``MCPMessage`` to serialize.

        Returns:
            A JSON string.
        """
        return message.model_dump_json(exclude_none=True, by_alias=False)

    def is_mcp_message(self, data: bytes) -> bool:
        """Heuristic check if the data is likely an MCP message.

        Checks if the data starts with ``{`` or ``[`` and contains
        ``"jsonrpc":"2.0"``.

        Args:
            data: Raw bytes to check.

        Returns:
            ``True`` if the data looks like an MCP message.
        """
        if not data:
            return False

        stripped = data.strip()
        if not stripped:
            return False

        # Must start with { (single) or [ (batch)
        if stripped[0:1] not in (b"{", b"["):
            return False

        # Must contain "jsonrpc":"2.0"
        try:
            text = stripped.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return False

        return '"jsonrpc":"2.0"' in text or '"jsonrpc": "2.0"' in text
