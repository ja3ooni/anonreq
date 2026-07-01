"""Streaming support package.

Contains the StreamEvent canonical model, TailBuffer FSM, and SSE
emitter for streaming LLM responses with real-time token restoration.
"""
"""Streaming support primitives."""

from anonreq.streaming.cleanup import SessionCleanup
from anonreq.streaming.emitter import SSEEmitter
from anonreq.streaming.restoration import StreamingRestorationStage
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent, ToolCallDelta
from anonreq.streaming.tail_buffer import BufferState, TailBuffer

__all__ = [
    "BufferState",
    "EventType",
    "FinishReason",
    "SSEEmitter",
    "SessionCleanup",
    "StreamEvent",
    "StreamingRestorationStage",
    "TailBuffer",
    "ToolCallDelta",
]
