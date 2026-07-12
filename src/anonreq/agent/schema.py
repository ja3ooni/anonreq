from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentContentType(StrEnum):
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"
    MCP_MESSAGE = "mcp_message"


ToolMessageType = Literal["openai", "anthropic", "mcp"]
InspectionAction = Literal["allow", "block", "sanitize"]


class ToolCall(BaseModel):
    model_config = {"extra": "forbid"}

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    id: str
    type: ToolMessageType


class ToolResult(BaseModel):
    model_config = {"extra": "forbid"}

    tool_name: str
    content: dict[str, Any] = Field(default_factory=dict)
    id: str
    type: ToolMessageType


class ToolArgumentSchema(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    type: str
    required: bool = False
    json_schema: dict[str, Any] = Field(default_factory=dict)


class InspectionResult(BaseModel):
    model_config = {"extra": "forbid"}

    action: InspectionAction
    reason: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    mitre_atlas_id: str | None = None
    audit_event_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
