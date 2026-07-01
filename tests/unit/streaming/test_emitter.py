"""Unit tests for SSE frame formatting."""

from __future__ import annotations

from anonreq.streaming.emitter import SSEEmitter
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent


def test_emits_text_delta_frame() -> None:
    frame = SSEEmitter().emit(
        StreamEvent(event_type=EventType.TEXT_DELTA, provider="test", delta_text="Hello")
    )
    assert frame.startswith("data: ")
    assert "Hello" in frame
    assert frame.endswith("\n\n")


def test_headers_are_sse_anti_buffering() -> None:
    headers = SSEEmitter().get_headers()
    assert headers["Content-Type"] == "text/event-stream"
    assert headers["X-Accel-Buffering"] == "no"


def test_finish_and_done_frames() -> None:
    emitter = SSEEmitter()
    frame = emitter.emit(
        StreamEvent(
            event_type=EventType.FINISH,
            provider="test",
            finish_reason=FinishReason.STOP,
        )
    )
    assert "finish_reason" in frame
    assert emitter.close_frame() == "data: [DONE]\n\n"
