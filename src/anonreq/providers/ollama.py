"""OllamaAdapter — OpenAI->Ollama message translation and stream normalization.

Per PROV-05 (Ollama local inference support):
- Translates OpenAI-compatible requests to Ollama Chat API format
- Executes HTTP calls to ``http://localhost:11434/api/chat``
- Normalises NDJSON streaming chunks to StreamEvent canonical model (AG-07)
- Normalises responses back to OpenAI-compatible chat completion format
- Error normalization per PROV-08 — no sensitive data in errors
"""

from __future__ import annotations

import json
import os
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

logger = structlog.get_logger("anonreq.providers.ollama")

_OLLAMA_DEFAULT_HOST = "http://localhost:11434"


def _ollama_base_url() -> str:
    """Return the configured Ollama base URL.

    Uses ``OLLAMA_HOST`` env var (Ollama's standard variable), falling back
    to ``http://localhost:11434``.
    """
    return os.environ.get("OLLAMA_HOST", _OLLAMA_DEFAULT_HOST).rstrip("/")


class OllamaAdapter(ProviderAdapter):
    """ProviderAdapter for Ollama local inference.

    Translates OpenAI-compatible requests to Ollama format,
    executes them, and normalises responses/streams back to
    the canonical format.
    """

    provider_name = "ollama"

    def __init__(self) -> None:
        self._capability_resolver = CapabilityResolver()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities for Ollama."""
        return self._capability_resolver.get_capabilities("ollama")

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
        """Translate an OpenAI-compatible request to Ollama format.

        Ollama uses an OpenAI-compatible messages format, so the
        translation is lightweight:
        - Messages are passed through as-is (including system messages)
        - The model name is mapped if needed
        - API key is used if set (remote Ollama deployments)
        """
        original: dict[str, Any] = ctx.original_request or {}

        body: dict[str, Any] = {
            "model": original.get("model", "llama3"),
            "messages": original.get("messages", []),
        }

        # Pass through optional params
        for param in ("temperature", "top_p", "top_k", "stream", "format", "options"):
            if param in original and original[param] is not None:
                body[param] = original[param]

        # Build URL using configured host
        base = _ollama_base_url()
        url = f"{base}/api/chat"

        # Headers
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }

        # Optional API key (for remote Ollama setups)
        try:
            api_key = resolve_api_key("ollama")
            headers["Authorization"] = f"Bearer {api_key}"
        except ValueError:
            pass  # No API key configured — Ollama runs locally without auth

        return ProviderRequest(
            url=url,
            headers=headers,
            body=body,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Execute a non-streaming HTTP POST to the Ollama API."""
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
                message="Ollama API timeout",
            )
        except httpx.ConnectError:
            raise PipelineAbortError(
                status_code=503,
                message="Ollama API unavailable — is the server running?",
            )
        except PipelineAbortError:
            raise
        except Exception as exc:
            raise PipelineAbortError(
                status_code=502,
                message=f"Ollama API error: {type(exc).__name__}",
            )

    # ------------------------------------------------------------------
    # stream_events
    # ------------------------------------------------------------------

    async def stream_events(
        self, request: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        """Execute a streaming POST and yield normalized StreamEvents.

        Ollama streaming returns **newline-delimited JSON (NDJSON)** —
        each line is a complete JSON object with a ``message`` field
        and a ``done`` boolean.
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

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    for stream_event in self._parse_ollama_chunk(data):
                        yield stream_event

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise PipelineAbortError(
                status_code=503,
                message=f"Ollama API stream error: {type(exc).__name__}",
            )

    def _parse_ollama_chunk(self, data: dict[str, Any]) -> list[StreamEvent]:
        """Parse a single Ollama NDJSON chunk into zero or more StreamEvents."""
        events: list[StreamEvent] = []

        message = data.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        role = message.get("role", "assistant") if isinstance(message, dict) else "assistant"

        if content:
            events.append(
                StreamEvent(
                    event_type=EventType.TEXT_DELTA,
                    provider=self.provider_name,
                    role=role,
                    delta_text=content,
                )
            )

        # Check for completion
        done = data.get("done", False)
        if done:
            done_reason = data.get("done_reason", "stop")
            finish_reason = self._map_finish_reason(done_reason)
            events.append(
                StreamEvent(
                    event_type=EventType.FINISH,
                    provider=self.provider_name,
                    role=role,
                    finish_reason=finish_reason,
                    metadata={"done_reason": done_reason},
                )
            )

        return events

    # ------------------------------------------------------------------
    # translate_response
    # ------------------------------------------------------------------

    def translate_response(
        self,
        ctx: Any,
        response: ProviderResponse,
    ) -> RestoredResponse:
        """Normalize an Ollama response to OpenAI-compatible format."""
        body = response.body

        # Extract message content
        message = body.get("message", {})
        content = ""
        finish_str = "stop"

        if isinstance(message, dict):
            content = message.get("content", "")

        # Determine finish reason
        done_reason = body.get("done_reason", "stop")
        if done_reason:
            finish_reason = self._map_finish_reason(done_reason)
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
                        "content": content,
                    },
                    "finish_reason": finish_str,
                }
            ],
        }

        # Include total duration if available
        if "total_duration" in body:
            canonical_body["usage"] = {
                "total_duration": body["total_duration"],
            }

        return RestoredResponse(body=canonical_body)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_finish_reason(reason: str) -> FinishReason:
        """Map an Ollama done_reason to canonical FinishReason."""
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
        }
        return mapping.get(reason, FinishReason.UNKNOWN)

    @staticmethod
    def _map_http_status(status_code: int) -> int:
        """Map provider HTTP status to appropriate gateway status.

        Always 502 (fail-secure) — never leak upstream info.
        """
        return 502

    def _normalize_error(self, response: httpx.Response) -> str:
        """Extract a safe error message from an Ollama error response."""
        try:
            error_data = response.json()
            # Ollama returns {"error": "message"}
            if isinstance(error_data, dict) and "error" in error_data:
                return f"Ollama API error: {type(error_data['error']).__name__}"
            return f"Ollama API returned HTTP {response.status_code}"
        except Exception:
            return f"Ollama API returned HTTP {response.status_code}"

    async def _normalize_error_async(self, response: httpx.Response) -> str:
        """Extract a safe error message during streaming (async version)."""
        try:
            error_data = json.loads(await response.aread())
            if isinstance(error_data, dict) and "error" in error_data:
                return f"Ollama API error: {type(error_data['error']).__name__}"
            return f"Ollama API returned HTTP {response.status_code}"
        except Exception:
            return f"Ollama API returned HTTP {response.status_code}"
