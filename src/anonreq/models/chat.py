"""OpenAI-compatible chat request/response Pydantic models.

Per PIPE-01, the gateway exposes ``POST /v1/chat/completions`` accepting
OpenAI-compatible payloads. These models define the wire format.

All models use ``model_config = {"extra": "ignore"}`` for forward
compatibility with OpenAI API changes (new fields may be added without
notice). Legacy fields (``functions``, ``function_call``) are omitted —
they are deprecated in the OpenAI API.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in the chat conversation.

    Matches the OpenAI Chat Completion message object schema.
    """

    role: Literal["system", "user", "assistant", "tool", "function"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    """OpenAI-compatible chat completion request body.

    All standard non-streaming fields are included.  ``stream`` defaults
    to ``False``.  Legacy fields (``functions``, ``function_call``) are
    omitted.
    """

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = 1
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict[str, float] | None = None
    user: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None

    model_config = {"extra": "ignore"}


class ChatCompletionChoice(BaseModel):
    """A single completion choice in the response."""

    index: int
    message: dict[str, Any]
    finish_reason: str | None = None

    model_config = {"extra": "ignore"}


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response body.

    Matches the non-streaming response schema from the OpenAI API.
    """

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: dict[str, int] | None = None

    model_config = {"extra": "ignore"}
