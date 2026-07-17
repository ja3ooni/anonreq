"""OpenAIAdapter — OpenAI-compatible request execution and stream normalization."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

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
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent, ToolCallDelta

_OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAIAdapter(ProviderAdapter):
    """ProviderAdapter for OpenAI's Chat Completions API."""

    provider_name = "openai"

    def __init__(self) -> None:
        self._capability_resolver = CapabilityResolver()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capability_resolver.get_capabilities("openai")

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        return self._http_client

    def translate_request(self, ctx: Any) -> ProviderRequest:
        original: dict[str, Any] = ctx.original_request or {}
        body = {
            key: value
            for key, value in original.items()
            if value is not None
        }

        api_key = resolve_api_key("openai")
        return ProviderRequest(
            url=f"{_OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout=30.0,
        )

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
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
            raise PipelineAbortError(status_code=504, message="OpenAI API timeout")  # noqa: B904
        except httpx.ConnectError:
            raise PipelineAbortError(status_code=503, message="OpenAI API unavailable")  # noqa: B904
        except PipelineAbortError:
            raise
        except httpx.HTTPStatusError as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"OpenAI API HTTP {exc.response.status_code}",
            )
        except httpx.RequestError as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"OpenAI API request error: {type(exc).__name__}",
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"OpenAI API response parse error: {type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=502,
                message=f"OpenAI API error: {type(exc).__name__}",
            )

    async def stream_events(self, request: ProviderRequest) -> AsyncIterator[StreamEvent]:
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
                    if not line or line.startswith(":") or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    for event in self._parse_chunk(data):
                        yield event

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise PipelineAbortError(  # noqa: B904
                status_code=503,
                message=f"OpenAI API stream error: {type(exc).__name__}",
            )

    def translate_response(self, _ctx: Any, response: ProviderResponse) -> RestoredResponse:
        return RestoredResponse(body=response.body, headers=response.headers)

    def _parse_chunk(self, data: dict[str, Any]) -> list[StreamEvent]:
        events: list[StreamEvent] = []
        choices = data.get("choices") or []
        for choice in choices:
            delta = choice.get("delta") or {}
            role = delta.get("role")
            content = delta.get("content")

            if role and not content:
                events.append(
                    StreamEvent(
                        event_type=EventType.START,
                        provider=self.provider_name,
                        role=role,
                        metadata={"id": data.get("id", ""), "model": data.get("model", "")},
                    )
                )

            if content:
                events.append(
                    StreamEvent(
                        event_type=EventType.TEXT_DELTA,
                        provider=self.provider_name,
                        role=role or "assistant",
                        delta_text=content,
                    )
                )

            for index, tool_call in enumerate(delta.get("tool_calls") or []):
                function = tool_call.get("function") or {}
                events.append(
                    StreamEvent(
                        event_type=EventType.TOOL_CALL_DELTA,
                        provider=self.provider_name,
                        role=role or "assistant",
                        tool_call=ToolCallDelta(
                            index=tool_call.get("index", index),
                            id=tool_call.get("id"),
                            type=tool_call.get("type"),
                            function_name=function.get("name"),
                            function_arguments=function.get("arguments"),
                        ),
                    )
                )

            finish_reason = choice.get("finish_reason")
            if finish_reason:
                events.append(
                    StreamEvent(
                        event_type=EventType.FINISH,
                        provider=self.provider_name,
                        role=role or "assistant",
                        finish_reason=self._map_finish_reason(finish_reason),
                        metadata={"finish_reason": finish_reason},
                    )
                )

        return events

    @staticmethod
    def _map_finish_reason(reason: str) -> FinishReason:
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "tool_calls": FinishReason.TOOL_CALL,
            "function_call": FinishReason.TOOL_CALL,
            "content_filter": FinishReason.CONTENT_FILTER,
        }
        return mapping.get(reason, FinishReason.UNKNOWN)

    @staticmethod
    def _map_http_status(status_code: int) -> int:
        if status_code == 408:
            return 504
        if status_code >= 500:
            return 502
        return 502

    def _normalize_error(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            error = data.get("error", {})
            error_type = error.get("type", "unknown_error")
            return f"OpenAI API error: {error_type}"
        except (json.JSONDecodeError, KeyError, TypeError):
            return f"OpenAI API returned HTTP {response.status_code}"

    async def _normalize_error_async(self, response: httpx.Response) -> str:
        try:
            data = json.loads(await response.aread())
            error = data.get("error", {})
            error_type = error.get("type", "unknown_error")
            return f"OpenAI API error: {error_type}"
        except (json.JSONDecodeError, KeyError, TypeError):
            return f"OpenAI API returned HTTP {response.status_code}"
