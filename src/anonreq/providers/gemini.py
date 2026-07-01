"""GeminiAdapter — OpenAI->Gemini message translation and stream normalization.

Per PROV-04 (Google Gemini support):
- Translates OpenAI-compatible requests to Gemini format
- Executes HTTP calls to ``https://generativelanguage.googleapis.com/...``
- Normalizes SSE events to StreamEvent canonical model (AG-07)
- Normalizes responses back to OpenAI-compatible chat completion format
- Error normalization per PROV-08 — no keys, URLs, or raw content in errors
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

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

logger = structlog.get_logger("anonreq.providers.gemini")

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter(ProviderAdapter):
    """ProviderAdapter for Google Gemini via the Generative Language API.

    Translates OpenAI-compatible requests to Gemini format,
    executes them, and normalises responses/streams back to
    the canonical format.
    """

    provider_name = "gemini"

    def __init__(self) -> None:
        self._capability_resolver = CapabilityResolver()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities for Gemini."""
        return self._capability_resolver.get_capabilities("gemini")

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialised shared HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    # ------------------------------------------------------------------
    # translate_request
    # ------------------------------------------------------------------

    def translate_request(self, ctx: Any) -> ProviderRequest:
        """Translate an OpenAI-compatible request to Gemini format.

        Per PROV-04:
        - System message is extracted to top-level ``system_instruction``
        - User/assistant messages become ``contents`` with roles ``user``/``model``
        - Tools are converted to ``function_declarations``
        - API key is resolved via ``x-goog-api-key`` header
        - Streaming uses the ``:streamGenerateContent`` endpoint variant
        """
        original: dict[str, Any] = ctx.original_request or {}
        messages: list[dict[str, Any]] = original.get("messages", [])

        # Separate system instruction
        system_text: str | None = None
        contents: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_text = content if isinstance(content, str) else str(content)
            else:
                # Map "assistant" -> "model" for Gemini
                gemini_role = "model" if role == "assistant" else role
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}] if isinstance(content, str) else content,
                })

        model_name = original.get("model", "gemini-pro")

        body: dict[str, Any] = {
            "model": model_name,
            "contents": contents,
        }

        if system_text:
            body["system_instruction"] = {
                "parts": [{"text": system_text}]
            }

        # Convert tools to Gemini function_declarations
        tools = original.get("tools")
        if tools:
            body["tools"] = [self._convert_tools(tools)]

        # Copy generation config
        gen_config: dict[str, Any] = {}
        for param in ("temperature", "top_p", "max_tokens", "stop"):
            if param in original and original[param] is not None:
                gen_config[param] = original[param]
        if gen_config:
            body["generationConfig"] = gen_config

        # API key
        api_key = resolve_api_key("gemini")

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        # Determine endpoint
        is_streaming = original.get("stream", False)
        if is_streaming:
            endpoint = f"{_GEMINI_BASE}/{model_name}:streamGenerateContent?alt=sse"
        else:
            endpoint = f"{_GEMINI_BASE}/{model_name}:generateContent"

        return ProviderRequest(
            url=endpoint,
            headers=headers,
            body=body,
            timeout=30.0,
        )

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Convert OpenAI tool definitions to Gemini ``function_declarations``."""
        declarations: list[dict[str, Any]] = []
        for tool in tools:
            func = tool.get("function", {})
            declarations.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
            })
        return {"function_declarations": declarations}

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Execute a non-streaming HTTP POST to the Gemini API."""
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
            raise PipelineAbortError(
                status_code=504,
                message="Gemini API timeout",
            )
        except httpx.ConnectError:
            raise PipelineAbortError(
                status_code=503,
                message="Gemini API unavailable",
            )
        except PipelineAbortError:
            raise
        except Exception as exc:
            raise PipelineAbortError(
                status_code=502,
                message=f"Gemini API error: {type(exc).__name__}",
            )

    # ------------------------------------------------------------------
    # stream_events
    # ------------------------------------------------------------------

    async def stream_events(
        self, request: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        """Execute a streaming HTTP POST and yield normalized StreamEvents.

        Gemini SSE uses ``data: {...}\n\n`` with no ``event:`` prefix.
        Each data line is a JSON object with a ``candidates`` array.
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

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    stream_event = self._parse_gemini_event(data)
                    if stream_event is not None:
                        yield stream_event

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise PipelineAbortError(
                status_code=503,
                message=f"Gemini API stream error: {type(exc).__name__}",
            )

    def _parse_gemini_event(self, data: dict[str, Any]) -> StreamEvent | None:
        """Parse a single Gemini SSE ``data:`` payload into a StreamEvent."""
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        candidate = candidates[0]
        content = candidate.get("content", {})
        role = content.get("role", "model")
        parts = content.get("parts", [])

        # Extract text from parts
        text_parts: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                text_parts.append(part.get("text", ""))

        full_text = "".join(text_parts)

        # Check for finish reason
        finish_reason_raw = candidate.get("finishReason")
        if finish_reason_raw:
            finish_reason = self._map_finish_reason(finish_reason_raw)
            return StreamEvent(
                event_type=EventType.FINISH,
                provider=self.provider_name,
                role=role,
                finish_reason=finish_reason,
                metadata={
                    "finishReason": finish_reason_raw,
                },
            )

        # Text delta
        if full_text:
            return StreamEvent(
                event_type=EventType.TEXT_DELTA,
                provider=self.provider_name,
                role=role,
                delta_text=full_text,
            )

        return None

    # ------------------------------------------------------------------
    # translate_response
    # ------------------------------------------------------------------

    def translate_response(
        self,
        ctx: Any,
        response: ProviderResponse,
    ) -> RestoredResponse:
        """Normalize a Gemini response to OpenAI-compatible format."""
        body = response.body

        # Extract text from candidates
        candidates = body.get("candidates", [])
        full_text = ""
        finish_str = "stop"

        if candidates:
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            text_parts: list[str] = []
            for part in parts:
                if isinstance(part, dict):
                    text_parts.append(part.get("text", ""))
            full_text = "".join(text_parts)

            finish_reason_raw = candidate.get("finishReason", "STOP")
            finish_reason = self._map_finish_reason(finish_reason_raw)
            finish_str = finish_reason.value.lower() if finish_reason else "stop"

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
        usage = body.get("usageMetadata")
        if usage:
            canonical_body["usage"] = usage

        return RestoredResponse(body=canonical_body)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_finish_reason(reason: str) -> FinishReason:
        """Map a Gemini finish reason to canonical FinishReason."""
        mapping = {
            "STOP": FinishReason.STOP,
            "MAX_TOKENS": FinishReason.LENGTH,
            "SAFETY": FinishReason.CONTENT_FILTER,
            "RECITATION": FinishReason.CONTENT_FILTER,
            "OTHER": FinishReason.UNKNOWN,
        }
        return mapping.get(reason, FinishReason.UNKNOWN)

    @staticmethod
    def _map_http_status(status_code: int) -> int:
        """Map provider HTTP status to appropriate gateway status.

        Always 502 (fail-secure) — never leak upstream auth/provider info.
        """
        return 502

    def _normalize_error(self, response: httpx.Response) -> str:
        """Extract a safe error message from a Gemini error response."""
        try:
            error_data = response.json()
            error_info = error_data.get("error", {})
            error_status = error_info.get("status", "UNKNOWN")
            return f"Gemini API error: {error_status}"
        except Exception:
            return f"Gemini API returned HTTP {response.status_code}"

    async def _normalize_error_async(self, response: httpx.Response) -> str:
        """Extract a safe error message during streaming (async version)."""
        try:
            error_data = json.loads(await response.aread())
            error_info = error_data.get("error", {})
            error_status = error_info.get("status", "UNKNOWN")
            return f"Gemini API error: {error_status}"
        except Exception:
            return f"Gemini API returned HTTP {response.status_code}"
