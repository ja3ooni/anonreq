"""StreamEvent canonical model for normalized provider streaming events.

Per D-54 through D-58:
- ``StreamEvent(BaseModel)`` is the canonical streaming event model
  used throughout the pipeline
- All provider streams are normalized to StreamEvent sequence (AG-07)
- Event types: START, TEXT_DELTA, TOOL_CALL_DELTA, REASONING_DELTA,
  FINISH, ERROR, HEARTBEAT
- Finish reasons normalized to: STOP, LENGTH, TOOL_CALL, CONTENT_FILTER,
  ERROR, UNKNOWN
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Canonical streaming event types.

    All provider-specific streaming events are normalized to one of
    these types (AG-07).
    """

    START = "START"
    TEXT_DELTA = "TEXT_DELTA"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    REASONING_DELTA = "REASONING_DELTA"
    FINISH = "FINISH"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"


class FinishReason(StrEnum):
    """Canonical finish reasons for stream termination.

    All provider-specific finish reasons are mapped to one of these
    values (D-57).
    """

    STOP = "STOP"
    LENGTH = "LENGTH"
    TOOL_CALL = "TOOL_CALL"
    CONTENT_FILTER = "CONTENT_FILTER"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class ToolCallDelta(BaseModel):
    """A delta for incremental tool call construction during streaming."""

    index: int
    id: str | None = None
    type: str | None = None  # "function"
    function_name: str | None = None
    function_arguments: str | None = None


class StreamEvent(BaseModel):
    """Canonical streaming event model.

    All provider streams normalize to a sequence of these events (AG-07).
    The TailBuffer FSM processes only TEXT_DELTA events — all other event
    types bypass the FSM (D-56).
    """

    event_type: EventType
    provider: str
    role: str | None = None
    delta_text: str | None = None
    tool_call: ToolCallDelta | None = None
    reasoning: str | None = None
    finish_reason: FinishReason | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}
