"""AnthropicAdapter — OpenAI->Anthropic message translation and stream normalization.

Per PROV-02 (Anthropic Claude support):
- Translates OpenAI-compatible requests to Anthropic Messages API format
- Executes HTTP calls to ``https://api.anthropic.com/v1/messages``
- Normalizes streaming SSE events to StreamEvent canonical model (AG-07)
- Normalizes responses back to OpenAI-compatible chat completion format
- Error normalization per PROV-08 — no keys, URLs, or raw content in errors
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog

from anonreq.exceptions import PipelineAbortError
from anonreq.providers.adapter import (
    ProviderAdapter,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    RestoredResponse,
)
from anonreq.providers.capabilities import CapabilityResolver
from anonreq.providers.registry import resolve_api_key
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent

logger = structlog.get_logger("anonreq.providers.anthropic")


class AnthropicAdapter(ProviderAdapter):
    """ProviderAdapter for Anthropic Claude via the Messages API.

    Translates OpenAI-compatible requests to Anthropic format,
    executes them, and normalizes responses/streams back to
    the canonical format.
    """

    provider_name = "anthropic"
    _BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self) -> None:
        self._capability_resolver = CapabilityResolver()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities for Anthropic Claude."""
        return self._capability_resolver.get_capabilities("anthropic")

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialised shared HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        return self._http_client

    # ------------------------------------------------------------------
    # translate_request
    # ------------------------------------------------------------------

    def translate_request(self, ctx: Any) -> ProviderRequest:
        """Translate an OpenAI-compatible request to Anthropic format.

        Per PROV-02:
        - System message is extracted to top-level ``system`` parameter
        - User/assistant messages keep ``role`` and ``content``
        - Tools are converted to Anthropic ``name``/``description``/``input_schema``
        - API key is resolved at the network boundary (AG-09)
        """
        original: dict[str, Any] = ctx.original_request or {}
        messages: list[dict[str, Any]] = original.get("messages", [])

        # Separate system message and convert messages
        system_content: str | None = None
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_content = content if isinstance(content, str) else str(content)
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": content,
                })

        # Build body
        body: dict[str, Any] = {
            "model": original.get("model", "claude-sonnet-4"),
            "messages": anthropic_messages,
        }

        if system_content:
            body["system"] = system_content

        # Convert tools to Anthropic format
        tools = original.get("tools")
        if tools:
            body["tools"] = [self._convert_tool(t) for t in tools]

        # Map tool_choice
        tool_choice = original.get("tool_choice")
        if tool_choice == "auto":
            body["tool_choice"] = {"type": "auto"}
        elif tool_choice == "required":
            body["tool_choice"] = {"type": "any"}
        elif tool_choice == "none":
            body["tool_choice"] = {"type": "none"}
        elif isinstance(tool_choice, dict):
            body["tool_choice"] = tool_choice

        # Copy other params
        for param in ("temperature", "top_p", "max_tokens", "stop", "stream"):
            if param in original and original[param] is not None:
                body[param] = original[param]

        # Resolve API key
        api_key = resolve_api_key("anthropic")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        return ProviderRequest(
            url=self._BASE_URL,
            headers=headers,
            body=body,
            timeout=30.0,
        )

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Convert an OpenAI tool definition to Anthropic format."""
        function = tool.get("function", {})
        return {
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {}),
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Execute a non-streaming HTTP POST to the Anthropic API."""
        try:
            response = await self._client.post(
                request.url,
                json=request.body,
                headers=request.headers,
            )

            if response.is_error:
                raise PipelineAbortError(
                    status_code=self._map_http_status(response.status_code),
                    message=self._normalize_error(response),
                )

            return ProviderResponse(
                status_code=response.status_code,
                body=response.json(),
                headers=dict(response.headers),
            )

        except httpx.TimeoutException:
            raise PipelineAbortError(  # noqa: B904
                status_code=504,
                message="Anthropic API timeout",
            )
        except httpx.ConnectError:
            raise PipelineAbortError(  # noqa: B904
                status_code=503,
                message="Anthropic API unavailable",
            )
        except PipelineAbortError:
            raise
        except httpx.HTTPStatusError as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"Anthropic API HTTP {exc.response.status_code}",
            )
        except httpx.RequestError as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"Anthropic API request error: {type(exc).__name__}",
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"Anthropic API response parse error: {type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"Anthropic API error: {type(exc).__name__}",
            )

    # ------------------------------------------------------------------
    # stream_events
    # ------------------------------------------------------------------

    async def stream_events(
        self, request: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        """Execute a streaming HTTP POST and yield normalized StreamEvents.

        Parses Anthropic SSE events per the Messages API streaming format:
        - ``content_block_delta`` with ``text_delta`` -> TEXT_DELTA
        - ``message_start`` -> START
        - ``message_delta`` with ``stop_reason`` -> FINISH
        - ``message_stop`` -> no event (stream finished)
        - ``error`` -> ERROR
        """
        try:
            async with self._client.stream(
                "POST",
                request.url,
                json=request.body,
                headers=request.headers,
            ) as response:
                if response.is_error:
                    error_msg = await self._normalize_error_async(response)
                    raise PipelineAbortError(
                        status_code=self._map_http_status(response.status_code),
                        message=error_msg,
                    )

                event_type = ""
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue

                    # Parse SSE format: "event: <type>" followed by "data: <json>"
                    if line.startswith("event: "):
                        event_type = line[7:]
                        continue
                    elif line.startswith("data: "):
                        data_str = line[6:]
                    else:
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    stream_event = self._parse_anthropic_event(event_type, data)
                    if stream_event is not None:
                        yield stream_event

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=503,
                message=f"Anthropic API stream error: {type(exc).__name__}",
            )

    def _parse_anthropic_event(
        self,
        sse_event_type: str,
        data: dict[str, Any],
    ) -> StreamEvent | None:
        """Parse a single Anthropic SSE event into a StreamEvent.

        Returns ``None`` for events that don't produce a StreamEvent
        (e.g. ping, content_block_stop without delta).
        """
        if sse_event_type == "message_start":
            return StreamEvent(
                event_type=EventType.START,
                provider=self.provider_name,
                role="assistant",
                metadata={"message_id": data.get("message", {}).get("id", "")},
            )

        elif sse_event_type == "content_block_delta":
            delta = data.get("delta", {})
            delta_type = delta.get("type")

            if delta_type == "text_delta":
                return StreamEvent(
                    event_type=EventType.TEXT_DELTA,
                    provider=self.provider_name,
                    role="assistant",
                    delta_text=delta.get("text", ""),
                )

            elif delta_type == "input_json_delta":
                # Tool use partial JSON
                return StreamEvent(
                    event_type=EventType.TOOL_CALL_DELTA,
                    provider=self.provider_name,
                    role="assistant",
                    metadata={"partial_json": delta.get("partial_json", "")},
                )

        elif sse_event_type == "message_delta":
            delta = data.get("delta", {})
            stop_reason = delta.get("stop_reason")

            if stop_reason:
                finish_reason = self._map_finish_reason(stop_reason)
                return StreamEvent(
                    event_type=EventType.FINISH,
                    provider=self.provider_name,
                    role="assistant",
                    finish_reason=finish_reason,
                    metadata={
                        "stop_reason": stop_reason,
                        "usage": data.get("usage", {}),
                    },
                )

        elif sse_event_type == "error":
            return StreamEvent(
                event_type=EventType.ERROR,
                provider=self.provider_name,
                metadata={"error": data.get("error", {})},
            )

        # message_stop, content_block_stop, content_block_start, ping -> no event
        return None

    # ------------------------------------------------------------------
    # translate_response
    # ------------------------------------------------------------------

    def translate_response(
        self,
        ctx: Any,
        response: ProviderResponse,
    ) -> RestoredResponse:
        """Normalize an Anthropic response to OpenAI-compatible format."""
        body = response.body

        # Extract text from Anthropic response content blocks
        content_blocks = body.get("content", [])
        text_parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        full_text = "".join(text_parts)

        # Determine finish reason
        stop_reason = body.get("stop_reason", "end_turn")
        finish_reason = self._map_finish_reason(stop_reason)
        finish_str = finish_reason.value.lower() if finish_reason else "stop"

        # Build OpenAI-compatible response
        canonical_body: dict[str, Any] = {
            "id": body.get("id", f"anonreq-{self.provider_name}"),
            "object": "chat.completion",
            "created": 0,
            "model": body.get("model", ctx.model if hasattr(ctx, "model") else ""),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_text,
                    },
                    "finish_reason": finish_str,
                }
            ],
        }

        # Include usage if available
        if "usage" in body:
            canonical_body["usage"] = body["usage"]

        return RestoredResponse(body=canonical_body)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_finish_reason(reason: str) -> FinishReason:
        """Map an Anthropic stop reason to canonical FinishReason."""
        mapping = {
            "end_turn": FinishReason.STOP,
            "stop_sequence": FinishReason.STOP,
            "max_tokens": FinishReason.LENGTH,
            "tool_use": FinishReason.TOOL_CALL,
        }
        return mapping.get(reason, FinishReason.UNKNOWN)

    @staticmethod
    def _map_http_status(status_code: int) -> int:
        """Map provider HTTP status to appropriate gateway status."""
        if status_code in (401, 403) or status_code == 429 or status_code >= 500:
            return 502
        return 502

    def _normalize_error(self, response: httpx.Response) -> str:
        """Extract a safe (no sensitive data) error message from an Anthropic error response."""
        try:
            error_data = response.json()
            error_info = error_data.get("error", {})
            error_type = error_info.get("type", "unknown_error")
            return f"Anthropic API error: {error_type}"
        except (json.JSONDecodeError, KeyError, TypeError):
            return f"Anthropic API returned HTTP {response.status_code}"

    async def _normalize_error_async(self, response: httpx.Response) -> str:
        """Extract a safe error message during streaming (async version).

        Uses ``await response.aread()`` to consume the streaming response
        body before parsing the error.
        """
        try:
            error_data = json.loads(await response.aread())
            error_info = error_data.get("error", {})
            error_type = error_info.get("type", "unknown_error")
            return f"Anthropic API error: {error_type}"
        except (json.JSONDecodeError, KeyError, TypeError):
            return f"Anthropic API returned HTTP {response.status_code}"
