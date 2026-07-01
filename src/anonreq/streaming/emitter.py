"""OpenAI-compatible Server-Sent Events formatting."""

from __future__ import annotations

import json
from typing import Any

from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent


class SSEEmitter:
    """Formats restored stream deltas as ``text/event-stream`` frames."""

    def emit(self, event: StreamEvent | str) -> str:
        if isinstance(event, str):
            payload: dict[str, Any] = {
                "choices": [{"delta": {"content": event}, "index": 0}]
            }
            return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"

        if event.event_type == EventType.TEXT_DELTA:
            payload = {"choices": [{"delta": {"content": event.delta_text or ""}, "index": 0}]}
        elif event.event_type == EventType.FINISH:
            reason = event.finish_reason or FinishReason.STOP
            reason_value = reason.value.lower() if isinstance(reason, FinishReason) else str(reason).lower()
            payload = {"choices": [{"delta": {}, "finish_reason": reason_value, "index": 0}]}
        elif event.event_type == EventType.ERROR:
            payload = {"error": {"message": event.metadata.get("message", "stream error"), "type": event.metadata.get("type", "provider_error")}}
        else:
            payload = {"choices": [{"delta": {}, "index": 0}]}
        return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"

    def get_headers(self) -> dict[str, str]:
        return {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Connection": "keep-alive",
        }

    def close_frame(self) -> str:
        return "data: [DONE]\n\n"
