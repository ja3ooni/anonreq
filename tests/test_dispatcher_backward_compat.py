"""Content-Type Dispatcher: backward compatibility & new content type routing.

Verifies the Phase 21 content-type routing contract:
- Existing ``application/json`` (chat/completion/rag) unchanged
- New content types: ``voice_stream``, ``agent_tool_call``,
  ``agent_tool_result``, ``mcp_message``
- Unknown content type → ``ROUTE_LOCAL`` (fail-closed, no forward)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.models import ContentType, UnifiedDetectionResult


@pytest.fixture
def dispatcher():
    json_mock = AsyncMock()
    json_mock.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.APPLICATION_JSON,
        analyzer_metadata={"raw_type": "application/json"},
    )
    multipart_mock = AsyncMock()
    multipart_mock.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.MULTIPART_FORM_DATA,
        analyzer_metadata={"raw_type": "multipart/form-data"},
    )
    return ContentTypeDispatcher(
        json_analyzer=json_mock,
        multipart_analyzer=multipart_mock,
    )


# ── Existing content types (backward compat) ──────────────────────


@pytest.mark.asyncio
async def test_dispatcher_handles_json_for_chat_completion_rag(dispatcher):
    """``application/json`` still returns json analyzer unchanged."""
    result = await dispatcher.dispatch("application/json", b'{"messages":[]}', None)
    assert result.content_type == ContentType.APPLICATION_JSON
    assert result.source_analyzer == "json_analyzer"
    assert result.should_process is True


@pytest.mark.asyncio
async def test_dispatcher_handles_multipart_for_multimodal(dispatcher):
    """``multipart/form-data`` still returns multipart analyzer unchanged."""
    result = await dispatcher.dispatch("multipart/form-data", b"--boundary\r\n", None)
    assert result.content_type == ContentType.MULTIPART_FORM_DATA
    assert result.source_analyzer == "multipart_analyzer"
    assert result.should_process is True


@pytest.mark.asyncio
async def test_dispatcher_handles_text_plain(dispatcher):
    """``text/plain`` still returns text analyzer path unchanged."""
    result = await dispatcher.dispatch("text/plain", b"hello world", None)
    assert result.content_type == ContentType.TEXT_PLAIN
    assert result.should_process is True


# ── New Phase 21 content types ────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_routes_voice_stream_audio_pcm(dispatcher):
    """``audio/pcm`` maps to VOICE_STREAM."""
    result = await dispatcher.dispatch("audio/pcm", b"\x00\x01", None)
    assert result.content_type == ContentType.VOICE_STREAM
    assert result.source_analyzer == "voice_stream"
    assert result.action == "ANONYMIZE"


@pytest.mark.asyncio
async def test_dispatcher_routes_voice_stream_audio_wav(dispatcher):
    """``audio/wav`` maps to VOICE_STREAM."""
    result = await dispatcher.dispatch("audio/wav", b"RIFF\x00\x00\x00\x00WAVE", None)
    assert result.content_type == ContentType.VOICE_STREAM


@pytest.mark.asyncio
async def test_dispatcher_routes_voice_stream_audio_opus(dispatcher):
    """``audio/opus`` maps to VOICE_STREAM."""
    result = await dispatcher.dispatch("audio/opus", b"OpusHead\x01", None)
    assert result.content_type == ContentType.VOICE_STREAM


@pytest.mark.asyncio
async def test_dispatcher_routes_agent_tool_call(dispatcher):
    """``application/x-anonreq-agent-tool-call`` maps to AGENT_TOOL_CALL."""
    result = await dispatcher.dispatch(
        "application/x-anonreq-agent-tool-call",
        b'{"tool_calls":[]}',
        None,
    )
    assert result.content_type == ContentType.AGENT_TOOL_CALL
    assert result.source_analyzer == "agent_tool_call"


@pytest.mark.asyncio
async def test_dispatcher_routes_agent_tool_result(dispatcher):
    """``application/x-anonreq-agent-tool-result`` maps to AGENT_TOOL_RESULT."""
    result = await dispatcher.dispatch(
        "application/x-anonreq-agent-tool-result",
        b'{"tool_outputs":{}}',
        None,
    )
    assert result.content_type == ContentType.AGENT_TOOL_RESULT
    assert result.source_analyzer == "agent_tool_result"
    assert result.action == "ANONYMIZE"


@pytest.mark.asyncio
async def test_dispatcher_routes_mcp_message(dispatcher):
    """``application/vnd.mcp+json`` maps to MCP_MESSAGE."""
    result = await dispatcher.dispatch(
        "application/vnd.mcp+json",
        b'{"jsonrpc":"2.0","method":"tools/call"}',
        None,
    )
    assert result.content_type == ContentType.MCP_MESSAGE
    assert result.source_analyzer == "mcp_message"


@pytest.mark.asyncio
async def test_dispatcher_routes_mcp_message_alt_header(dispatcher):
    """``application/x-anonreq-mcp`` also maps to MCP_MESSAGE."""
    result = await dispatcher.dispatch(
        "application/x-anonreq-mcp",
        b'{"jsonrpc":"2.0"}',
        None,
    )
    assert result.content_type == ContentType.MCP_MESSAGE


# ── Unknown content type ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_unknown_content_type_returns_route_local(dispatcher):
    """Unknown content type returns ROUTE_LOCAL (fail-closed)."""
    result = await dispatcher.dispatch("application/octet-stream", b"\x00\x01\x02", None)
    assert result.content_type == ContentType.UNKNOWN
    assert result.source_analyzer == "dispatcher"
    assert result.should_process is False
    assert result.action == "ROUTE_LOCAL"


@pytest.mark.asyncio
async def test_dispatcher_empty_content_type_defaults_to_text(dispatcher):
    """Empty/blank content type defaults to text/plain."""
    result = await dispatcher.dispatch("", b"plain text", None)
    assert result.content_type == ContentType.TEXT_PLAIN


@pytest.mark.asyncio
async def test_dispatcher_unknown_raw_type_recorded_in_metadata(dispatcher):
    """UNKNOWN result includes raw_type in analyzer_metadata."""
    result = await dispatcher.dispatch("application/x-custom", b"data", None)
    assert result.content_type == ContentType.UNKNOWN
    assert result.detection_result.analyzer_metadata["raw_type"] == "application/x-custom"
