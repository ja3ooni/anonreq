from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ContentType(StrEnum):
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    MULTIPART_FORM_DATA = "multipart/form-data"
    VOICE_STREAM = "voice_stream"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"
    MCP_MESSAGE = "mcp_message"
    UNKNOWN = "unknown"


class UnifiedDetectionResult(BaseModel):
    content_type: ContentType
    entities: list[dict[str, Any]] = Field(default_factory=list)
    risk_score: float = 0.0
    classification: str = "Internal"
    analyzer_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyzerResult(BaseModel):
    source_analyzer: str
    content_type: ContentType
    detection_result: UnifiedDetectionResult
    should_process: bool = True
    action: str = "ANONYMIZE"
