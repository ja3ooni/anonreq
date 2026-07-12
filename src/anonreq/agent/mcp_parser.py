from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from anonreq.agent.schema import ToolCall, ToolResult

MCP_MESSAGE_TYPES = {
    "initialize",
    "tool_call",
    "tool_result",
    "resource_request",
    "resource_response",
    "tools/list",
    "tools/call",
    "resources/read",
    "notifications/tools/list_changed",
}


class MCPParseError(ValueError):
    """Raised when a message looks like MCP but cannot be parsed safely."""


class MCPMessage(BaseModel):
    model_config = {"extra": "forbid"}

    message_type: str
    message_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    protocol_version: str = "unknown"
    raw_method: str | None = None


class MCPParser:
    async def parse(self, data: bytes) -> MCPMessage | None:
        raw = data.decode("utf-8", errors="strict")
        try:
            frame = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MCPParseError("Malformed MCP JSON frame") from exc

        if not isinstance(frame, dict):
            raise MCPParseError("MCP frame must be a JSON object")

        if frame.get("jsonrpc") == "2.0":
            return self._parse_jsonrpc_frame(frame)

        if "type" in frame:
            return self._parse_typed_frame(frame)

        return None

    async def parse_tool_call(self, msg: MCPMessage | None) -> ToolCall | None:
        if msg is None or msg.message_type != "tool_call":
            return None

        payload = msg.payload
        function = payload.get("function")
        if isinstance(function, dict):
            tool_name = str(function.get("name") or payload.get("name") or "unknown")
            raw_args = function.get("arguments", payload.get("arguments", {}))
        else:
            tool_name = str(payload.get("name") or "unknown")
            raw_args = payload.get("arguments", {})

        return ToolCall(
            tool_name=tool_name,
            arguments=self._coerce_arguments(raw_args),
            id=msg.message_id,
            type="mcp",
        )

    async def parse_tool_result(self, msg: MCPMessage | None) -> ToolResult | None:
        if msg is None or msg.message_type != "tool_result":
            return None

        content = msg.payload.get("content", {})
        if isinstance(content, list):
            content_dict: dict[str, Any] = {"items": content}
        elif isinstance(content, dict):
            content_dict = content
        else:
            content_dict = {"value": content}

        return ToolResult(
            tool_name=str(msg.payload.get("name") or msg.payload.get("tool_name") or "unknown"),
            content=content_dict,
            id=msg.message_id,
            type="mcp",
        )

    def format_error(self, tool_call_id: str, error_msg: str) -> dict[str, Any]:
        digest = hashlib.sha256(error_msg.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return {
            "jsonrpc": "2.0",
            "id": tool_call_id,
            "error": {
                "code": "mcp_protocol_violation",
                "message": "MCP message rejected by AnonReq",
                "metadata": {"error_hash": digest},
            },
        }

    def _parse_jsonrpc_frame(self, frame: dict[str, Any]) -> MCPMessage | None:
        method = frame.get("method")
        payload: dict[str, Any]
        message_type: str

        if method == "initialize":
            params = self._dict_or_empty(frame.get("params"))
            return MCPMessage(
                message_type="initialize",
                message_id=self._message_id(frame),
                payload=params,
                protocol_version=str(params.get("protocolVersion") or "unknown"),
                raw_method=method,
            )

        if method == "tools/call":
            payload = self._dict_or_empty(frame.get("params"))
            message_type = "tool_call"
        elif "result" in frame:
            payload = self._dict_or_empty(frame.get("result"))
            message_type = "tool_result"
        else:
            if method in MCP_MESSAGE_TYPES:
                payload = self._dict_or_empty(frame.get("params"))
                message_type = str(method)
            else:
                return None

        return MCPMessage(
            message_type=message_type,
            message_id=self._message_id(frame),
            payload=payload,
            protocol_version=str(
                payload.get("protocolVersion")
                or frame.get("protocolVersion")
                or "unknown"
            ),
            raw_method=str(method) if method else None,
        )

    def _parse_typed_frame(self, frame: dict[str, Any]) -> MCPMessage | None:
        message_type = str(frame.get("type"))
        if message_type not in MCP_MESSAGE_TYPES:
            return None
        if message_type == "tools/call":
            message_type = "tool_call"

        payload = self._dict_or_empty(frame.get("payload") or frame.get("params"))
        return MCPMessage(
            message_type=message_type,
            message_id=self._message_id(frame),
            payload=payload,
            protocol_version=str(frame.get("protocolVersion") or payload.get("protocolVersion") or "unknown"),  # noqa: E501
            raw_method=str(frame.get("method")) if frame.get("method") else None,
        )

    def _coerce_arguments(self, raw_args: Any) -> dict[str, Any]:
        if raw_args is None:
            return {}
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                return {"_raw": raw_args}
            return parsed if isinstance(parsed, dict) else {"_value": parsed}
        return {"_value": raw_args}

    def _dict_or_empty(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _message_id(self, frame: dict[str, Any]) -> str:
        value = frame.get("id") or frame.get("message_id") or frame.get("messageId")
        return str(value) if value is not None else "unknown"
