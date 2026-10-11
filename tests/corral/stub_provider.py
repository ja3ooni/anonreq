"""A stand-in LLM provider for gateway integration tests.

It records every request body it receives so a test can assert what the
provider actually saw, and answers with text that echoes the (sanitized)
prompt, so token restoration can be checked end to end.

Run:  uvicorn stub_provider:app --port 8081
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
received: list[dict[str, Any]] = []


def _last_user_text(body: dict[str, Any]) -> str:
    for message in reversed(body.get("messages", [])):
        if message.get("role") == "user":
            content = message.get("content", "")
            return content if isinstance(content, str) else json.dumps(content)
    return ""


@app.get("/__received")
async def get_received() -> list[dict[str, Any]]:
    return received


@app.post("/__reset")
async def reset() -> dict[str, int]:
    received.clear()
    return {"cleared": 1}


@app.post("/v1/chat/completions")
async def chat(request: Request) -> Any:
    body = await request.json()
    received.append({"headers": {"authorization": request.headers.get("authorization", "")}, "body": body})
    reply = f"Echo: {_last_user_text(body)}"

    if not body.get("stream"):
        return JSONResponse(
            {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model", "stub"),
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    async def events() -> AsyncIterator[str]:
        # Three characters per chunk so tokens such as [EMAIL_1] are split across chunks.
        for i in range(0, len(reply), 3):
            chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": body.get("model", "stub"),
                "choices": [{"index": 0, "delta": {"content": reply[i : i + 3]}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
        done = {
            "id": "chatcmpl-stub",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": body.get("model", "stub"),
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(done)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
