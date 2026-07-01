"""ADAPT-01 through ADAPT-04 tests for all provider adapters.

Test suites:
- ADAPT-01: Canonical request -> provider request translation
- ADAPT-02: Provider response -> canonical response translation
- ADAPT-03: Provider stream -> StreamEvent normalization
- ADAPT-04: Error normalization across providers (no keys, URLs, or raw content)

Requires ``respx`` for HTTP mocking and the provider-specific async
HTTP calls.
"""

from __future__ import annotations

import os
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from anonreq.providers.adapter import (
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    RestoredResponse,
)
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def openai_chat_request() -> dict[str, Any]:
    """A minimal OpenAI-compatible chat request for test inputs."""
    return {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"},
        ],
        "stream": False,
        "temperature": 0.7,
    }


@pytest.fixture
def processing_context(openai_chat_request):
    """A minimal ProcessingContext-like dict for adapter testing."""
    from anonreq.models.processing_context import ProcessingContext

    ctx = ProcessingContext(request_id="test_req_001")
    ctx.original_request = openai_chat_request
    ctx.provider = "anthropic"
    ctx.model = "claude-sonnet-4"
    return ctx


@pytest.fixture
def ctx_with_tools(openai_chat_request):
    """A ProcessingContext with tools in the request."""
    from anonreq.models.processing_context import ProcessingContext

    ctx = ProcessingContext(request_id="test_req_002")
    ctx.original_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What's the weather in London?"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "unit": {"type": "string", "enum": ["c", "f"]},
                        },
                    },
                },
            }
        ],
        "tool_choice": "auto",
    }
    ctx.provider = "anthropic"
    ctx.model = "claude-sonnet-4"
    return ctx


# =========================================================================
# ADAPT-01: Canonical request -> provider request translation
# =========================================================================


class TestAnthropicTranslateRequest:
    """Tests for AnthropicAdapter.translate_request()."""

    def test_translate_basic_messages(self, processing_context):
        """Test 1: Basic OpenAI messages are converted to Anthropic format."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()
        request = adapter.translate_request(processing_context)

        assert isinstance(request, ProviderRequest)
        assert request.url == "https://api.anthropic.com/v1/messages"
        assert "x-api-key" in request.headers
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert request.method == "POST"
        assert request.timeout == 30.0

        body = request.body
        assert "model" in body
        assert "messages" in body

        # Messages should not include system message
        messages = body["messages"]
        assert len(messages) == 2  # user + assistant, no system
        assert all(m["role"] in ("user", "assistant") for m in messages)

    def test_system_message_to_system_param(self, processing_context):
        """Test 2: System message should become top-level ``system`` param."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()
        request = adapter.translate_request(processing_context)

        assert "system" in request.body
        assert request.body["system"] == "You are a helpful assistant."

    def test_tool_choice_and_tools(self, ctx_with_tools):
        """Test 3: Tools are converted to Anthropic tool format."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()
        request = adapter.translate_request(ctx_with_tools)

        body = request.body
        assert "tools" in body
        assert len(body["tools"]) == 1

        tool = body["tools"][0]
        assert tool["name"] == "get_weather"
        assert "description" in tool
        assert "input_schema" in tool
        assert "type" not in tool  # Anthropic doesn't use "type"="function"

    def test_api_key_resolution(self, processing_context):
        """Test 10: API key is resolved via env var."""
        from anonreq.providers.anthropic import AnthropicAdapter

        with patch.dict(os.environ, {"ANONREQ_ANTHROPIC_API_KEY": "sk-ant-test123"}):
            adapter = AnthropicAdapter()
            request = adapter.translate_request(processing_context)
            assert request.headers["x-api-key"] == "sk-ant-test123"


# =========================================================================
# ADAPT-02: Provider response -> canonical response translation
# =========================================================================


class TestAnthropicTranslateResponse:
    """Tests for AnthropicAdapter.translate_response()."""

    def test_translate_response_basic(self, processing_context):
        """Test 8: Anthropic response is normalized to canonical format."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()
        anthropic_response = ProviderResponse(
            status_code=200,
            body={
                "id": "msg_01abc123",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello! I'm doing well."}],
                "model": "claude-sonnet-4",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

        result = adapter.translate_response(processing_context, anthropic_response)

        assert isinstance(result, RestoredResponse)
        body = result.body
        assert "choices" in body
        assert len(body["choices"]) == 1
        assert body["choices"][0]["message"]["content"] == "Hello! I'm doing well."
        assert body["choices"][0]["finish_reason"] == "stop"


# =========================================================================
# ADAPT-03: Provider stream -> StreamEvent normalization
# =========================================================================


class TestAnthropicStreamEvents:
    """Tests for AnthropicAdapter.stream_events()."""

    @pytest.mark.asyncio
    async def test_stream_events_text_delta(self):
        """Test 5: content_block_delta with text_delta -> TEXT_DELTA event."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()

        # Mock SSE event data
        sse_data = (
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","index":0,'
            b'"delta":{"type":"text_delta","text":"Hello"}}\n\n'
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","index":0,'
            b'"delta":{"type":"text_delta","text":" world"}}\n\n'
            b'event: message_stop\n'
            b'data: {"type":"message_stop"}\n\n'
        )

        with respx.mock:
            route = respx.post("https://api.anthropic.com/v1/messages")
            route.mock(
                return_value=Response(
                    200,
                    content=sse_data,
                    headers={"Content-Type": "text/event-stream"},
                )
            )

            request = ProviderRequest(
                url="https://api.anthropic.com/v1/messages",
                headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
                body={"model": "claude-sonnet-4", "messages": [], "stream": True},
            )

            events = []
            async for event in adapter.stream_events(request):
                events.append(event)

            assert len(events) >= 2
            # Check TEXT_DELTA events
            text_events = [e for e in events if e.event_type == EventType.TEXT_DELTA]
            assert len(text_events) >= 2

    @pytest.mark.asyncio
    async def test_stream_events_finish_stop(self):
        """Test 6: message_stop -> FINISH with STOP reason."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()

        sse_data = (
            b'event: message_start\n'
            b'data: {"type":"message_start","message":{"id":"msg_1","role":"assistant"}}\n\n'
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","index":0,'
            b'"delta":{"type":"text_delta","text":"Hello"}}\n\n'
            b'event: message_delta\n'
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
            b'event: message_stop\n'
            b'data: {"type":"message_stop"}\n\n'
        )

        with respx.mock:
            route = respx.post("https://api.anthropic.com/v1/messages")
            route.mock(
                return_value=Response(
                    200,
                    content=sse_data,
                    headers={"Content-Type": "text/event-stream"},
                )
            )

            request = ProviderRequest(
                url="https://api.anthropic.com/v1/messages",
                headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
                body={"model": "claude-sonnet-4", "messages": [], "stream": True},
            )

            events = []
            async for event in adapter.stream_events(request):
                events.append(event)

            finish_events = [e for e in events if e.event_type == EventType.FINISH]
            assert len(finish_events) >= 1
            assert finish_events[0].finish_reason == FinishReason.STOP


# =========================================================================
# ADAPT-04: Error normalization across providers
# =========================================================================


class TestAnthropicErrorNormalization:
    """Tests for error normalization per PROV-08."""

    SENSITIVE_PATTERNS = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # Anthropic API keys
        re.compile(r"http[s]?://[^\s]+"),  # URLs
        re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),  # Base64 content
    ]

    def assert_no_sensitive_data(self, error_msg: str, context: str = ""):
        """Assert that an error message contains no sensitive patterns."""
        for pattern in self.SENSITIVE_PATTERNS:
            match = pattern.search(error_msg)
            if match:
                pytest.fail(
                    f"Sensitive pattern '{pattern.pattern}' found in error: "
                    f"'{error_msg[:200]}' (context: {context})"
                    f" — matched: '{match.group()[:50]}'"
                )

    @pytest.mark.asyncio
    async def test_auth_error_normalized(self, processing_context):
        """Auth errors should be normalized with no keys or URLs."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()

        with patch.dict(os.environ, {"ANONREQ_ANTHROPIC_API_KEY": "sk-test-invalid"}):
            request = adapter.translate_request(processing_context)

            with respx.mock:
                route = respx.post("https://api.anthropic.com/v1/messages")
                route.mock(
                    return_value=Response(
                        401,
                        json={
                            "error": {
                                "type": "authentication_error",
                                "message": "Invalid API key: sk-ant-invalid-key-value-here",
                            }
                        },
                    )
                )

                with pytest.raises(Exception) as exc_info:
                    await adapter.execute(request)

                error_msg = str(exc_info.value)
                self.assert_no_sensitive_data(
                    error_msg, context="anthropic auth error"
                )
                # Should still indicate it's an auth error
                assert any(
                    word in error_msg.lower()
                    for word in ["auth", "unauthorized", "401", "key", "credential"]
                ), f"Error message should indicate auth issue: {error_msg}"

    @pytest.mark.asyncio
    async def test_rate_limit_error_normalized(self, processing_context):
        """Rate limit errors should be normalized with no sensitive data."""
        from anonreq.providers.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()

        with patch.dict(os.environ, {"ANONREQ_ANTHROPIC_API_KEY": "sk-test-key"}):
            request = adapter.translate_request(processing_context)

            with respx.mock:
                route = respx.post("https://api.anthropic.com/v1/messages")
                route.mock(
                    return_value=Response(
                        429,
                        json={
                            "error": {
                                "type": "rate_limit_error",
                                "message": "Rate limit exceeded for org_12345",
                            }
                        },
                    )
                )

                with pytest.raises(Exception) as exc_info:
                    await adapter.execute(request)

                error_msg = str(exc_info.value)
                self.assert_no_sensitive_data(
                    error_msg, context="anthropic rate limit error"
                )


# =========================================================================
# GeminiAdapter tests
# =========================================================================


class TestGeminiTranslateRequest:
    """Tests for GeminiAdapter.translate_request()."""

    def test_translate_basic_messages(self, processing_context):
        """Basic OpenAI messages are converted to Gemini format."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        request = adapter.translate_request(processing_context)

        assert isinstance(request, ProviderRequest)
        assert "generativelanguage.googleapis.com" in request.url
        assert "x-goog-api-key" in request.headers
        assert request.method == "POST"
        assert request.timeout == 30.0

        body = request.body
        assert "model" in body
        assert "contents" in body

        # Messages should exclude system (it's in system_instruction)
        messages = body["contents"]
        assert len(messages) == 2  # user + assistant
        # Gemini uses "model" role, not "assistant"
        assert messages[0]["role"] == "user"
        assert messages[-1]["role"] == "model"
        # Each content should have parts array with text
        assert "parts" in messages[0]
        assert "text" in messages[0]["parts"][0]

    def test_system_message_to_system_instruction(self, processing_context):
        """System message should become top-level ``system_instruction``."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        request = adapter.translate_request(processing_context)

        assert "system_instruction" in request.body
        parts = request.body["system_instruction"]["parts"]
        assert any(
            "You are a helpful assistant." in p.get("text", "") for p in parts
        )

    def test_tool_choice_and_tools(self, ctx_with_tools):
        """Tools are converted to Gemini ``function_declarations``."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        request = adapter.translate_request(ctx_with_tools)

        body = request.body
        assert "tools" in body
        assert "function_declarations" in body["tools"][0]

        declarations = body["tools"][0]["function_declarations"]
        assert len(declarations) == 1
        decl = declarations[0]
        assert decl["name"] == "get_weather"
        assert "description" in decl
        assert "parameters" in decl

    def test_api_key_resolution(self, processing_context):
        """API key is resolved via env var."""
        import os
        from unittest.mock import patch

        from anonreq.providers.gemini import GeminiAdapter

        with patch.dict(os.environ, {"ANONREQ_GEMINI_API_KEY": "test-gemini-key-123"}):
            adapter = GeminiAdapter()
            request = adapter.translate_request(processing_context)
            assert request.headers["x-goog-api-key"] == "test-gemini-key-123"


class TestGeminiTranslateResponse:
    """Tests for GeminiAdapter.translate_response()."""

    def test_translate_response_basic(self, processing_context):
        """Gemini response is normalized to canonical format."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        gemini_response = ProviderResponse(
            status_code=200,
            body={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Hello! I'm doing well."}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                },
            },
        )

        result = adapter.translate_response(processing_context, gemini_response)

        assert isinstance(result, RestoredResponse)
        body = result.body
        assert "choices" in body
        assert len(body["choices"]) == 1
        assert body["choices"][0]["message"]["content"] == "Hello! I'm doing well."
        assert body["choices"][0]["finish_reason"] == "stop"


class TestGeminiStreamEvents:
    """Tests for GeminiAdapter.stream_events()."""

    @pytest.mark.asyncio
    async def test_stream_events_text_delta(self):
        """Gemini SSE text chunks -> TEXT_DELTA event."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        # Gemini SSE uses "data: {...}" (no "event:" prefix)
        sse_data = (
            b'data: {"candidates":[{"index":0,"content":{"role":"model",'
            b'"parts":[{"text":"Hello"}]}}]}\n\n'
            b'data: {"candidates":[{"index":0,"content":{"role":"model",'
            b'"parts":[{"text":" world"}]}}]}\n\n'
        )

        stream_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-pro:streamGenerateContent?alt=sse"
        )

        with respx.mock:
            route = respx.post(stream_url)
            route.mock(
                return_value=Response(
                    200,
                    content=sse_data,
                    headers={"Content-Type": "text/event-stream"},
                )
            )

            request = ProviderRequest(
                url=stream_url,
                headers={
                    "x-goog-api-key": "test-key",
                    "Content-Type": "application/json",
                },
                body={"model": "gemini-pro", "contents": [], "stream": True},
            )

            events = []
            async for event in adapter.stream_events(request):
                events.append(event)

            assert len(events) >= 2
            text_events = [e for e in events if e.event_type == EventType.TEXT_DELTA]
            assert len(text_events) >= 2

    @pytest.mark.asyncio
    async def test_stream_events_finish_stop(self):
        """Gemini finishReason -> FINISH with STOP reason."""
        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        sse_data = (
            b'data: {"candidates":[{"index":0,"content":{"role":"model",'
            b'"parts":[{"text":"Hello"}]}}]}\n\n'
            b'data: {"candidates":[{"index":0,"content":{"role":"model",'
            b'"parts":[{"text":" world"}]},"finishReason":"STOP"}]}\n\n'
        )

        stream_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-pro:streamGenerateContent?alt=sse"
        )

        with respx.mock:
            route = respx.post(stream_url)
            route.mock(
                return_value=Response(
                    200,
                    content=sse_data,
                    headers={"Content-Type": "text/event-stream"},
                )
            )

            request = ProviderRequest(
                url=stream_url,
                headers={
                    "x-goog-api-key": "test-key",
                    "Content-Type": "application/json",
                },
                body={"model": "gemini-pro", "contents": [], "stream": True},
            )

            events = []
            async for event in adapter.stream_events(request):
                events.append(event)

            finish_events = [e for e in events if e.event_type == EventType.FINISH]
            assert len(finish_events) >= 1
            assert finish_events[0].finish_reason == FinishReason.STOP


class TestGeminiErrorNormalization:
    """Tests for Gemini error normalization per PROV-08."""

    SENSITIVE_PATTERNS = TestAnthropicErrorNormalization.SENSITIVE_PATTERNS
    assert_no_sensitive_data = TestAnthropicErrorNormalization.assert_no_sensitive_data

    @pytest.mark.asyncio
    async def test_auth_error_normalized(self, processing_context):
        """Auth errors should be normalized with no keys."""
        import os
        from unittest.mock import patch

        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        with patch.dict(os.environ, {"ANONREQ_GEMINI_API_KEY": "test-invalid-key"}):
            request = adapter.translate_request(processing_context)

            # Non-streaming URL
            execute_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-pro:generateContent"
            )

            with respx.mock:
                route = respx.post(execute_url)
                route.mock(
                    return_value=Response(
                        401,
                        json={
                            "error": {
                                "code": 401,
                                "message": "API_KEY_INVALID: Invalid API key",
                                "status": "UNAUTHENTICATED",
                            }
                        },
                    )
                )

                with pytest.raises(Exception) as exc_info:
                    await adapter.execute(request)

                error_msg = str(exc_info.value)
                self.assert_no_sensitive_data(
                    error_msg, context="gemini auth error"
                )

    @pytest.mark.asyncio
    async def test_rate_limit_error_normalized(self, processing_context):
        """Rate limit errors should be normalized."""
        import os
        from unittest.mock import patch

        from anonreq.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        with patch.dict(os.environ, {"ANONREQ_GEMINI_API_KEY": "test-key"}):
            request = adapter.translate_request(processing_context)

            # Non-streaming URL
            execute_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-pro:generateContent"
            )

            with respx.mock:
                route = respx.post(execute_url)
                route.mock(
                    return_value=Response(
                        429,
                        json={
                            "error": {
                                "code": 429,
                                "message": "Rate limit exceeded for project_12345",
                                "status": "RESOURCE_EXHAUSTED",
                            }
                        },
                    )
                )

                with pytest.raises(Exception) as exc_info:
                    await adapter.execute(request)

                error_msg = str(exc_info.value)
                self.assert_no_sensitive_data(
                    error_msg, context="gemini rate limit error"
                )
