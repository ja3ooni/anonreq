from __future__ import annotations

import pytest

from anonreq.voice.config import VoiceConfig
from anonreq.voice.connectors import (
    AudioChunk,
    GRPCConnector,
    SIPConnector,
    WebRTCConnector,
    WebSocketConnector,
)


@pytest.fixture
def delivered_chunks():
    chunks: list[AudioChunk] = []

    async def callback(chunk: AudioChunk) -> None:
        chunks.append(chunk)

    return chunks, callback


class TestVoiceConfig:
    def test_default_voice_config_matches_phase_contract(self):
        cfg = VoiceConfig()
        assert cfg.stt_model_size == "base"
        assert cfg.stt_device == "auto"
        assert cfg.audio_sample_rate == 16000
        assert cfg.sliding_window_ms == 500
        assert cfg.window_overlap_ms == 125
        assert cfg.latency_budget_ms == 150
        assert cfg.supported_audio_formats == ("pcm", "wav", "opus")

    def test_invalid_overlap_rejected(self):
        with pytest.raises(ValueError):
            VoiceConfig(sliding_window_ms=500, window_overlap_ms=500)


@pytest.mark.asyncio
async def test_content_type_dispatcher_recognizes_voice_stream():
    from unittest.mock import AsyncMock

    from anonreq.multimodal.dispatcher import ContentTypeDispatcher
    from anonreq.multimodal.models import ContentType

    dispatcher = ContentTypeDispatcher(
        json_analyzer=AsyncMock(),
        multipart_analyzer=AsyncMock(),
    )

    result = await dispatcher.dispatch("audio/pcm", b"\x00\x00", None)

    assert result.content_type == ContentType.VOICE_STREAM
    assert result.source_analyzer == "voice_stream"
    assert result.action == "ANONYMIZE"


class TestFormatDetection:
    def test_detects_pcm_wav_and_opus(self, delivered_chunks):
        _, callback = delivered_chunks
        connector = WebSocketConnector(callback)

        assert connector.detect_audio_format({"content-type": "audio/pcm"}, b"\x00\x01") == "pcm"
        assert connector.detect_audio_format({}, b"RIFF\x24\x00\x00\x00WAVEfmt ") == "wav"
        assert connector.detect_audio_format({"content-type": "audio/opus"}, b"payload") == "opus"
        assert connector.detect_audio_format({"rtpmap": "111 opus/48000/2"}, b"payload") == "opus"


class TestSIPConnector:
    @pytest.mark.asyncio
    async def test_sip_connector_proxies_invite_and_extracts_rtp(self, delivered_chunks):
        chunks, callback = delivered_chunks
        connector = SIPConnector(callback)
        await connector.start()

        invite = (
            b"INVITE sip:bob@example.com SIP/2.0\r\n"
            b"Via: SIP/2.0/UDP proxy.example.com\r\n"
            b"From: <sip:alice@example.com>\r\n"
            b"To: <sip:bob@example.com>\r\n"
            b"Call-ID: abc123\r\n"
            b"m=audio 49170 RTP/AVP 111\r\n"
            b"a=rtpmap:111 opus/48000/2\r\n"
        )
        info = await connector.proxy_sip_message(invite)
        rtp = bytes([0x80, 0xE0]) + b"\x00" * 10 + b"opus-payload"
        chunk = await connector.extract_rtp_packet(rtp, timestamp_ms=100)

        assert info["is_invite"] is True
        assert info["codec"] == "opus"
        assert info["routing_headers_preserved"] is True
        assert chunk.format == "opus"
        assert chunk.data == b"opus-payload"
        assert chunks == [chunk]


class TestWebRTCConnector:
    @pytest.mark.asyncio
    async def test_webrtc_connector_inspects_sdp_and_extracts_audio_tracks(self, delivered_chunks):
        chunks, callback = delivered_chunks
        connector = WebRTCConnector(callback)
        await connector.start()
        sdp = "\n".join(
            [
                "v=0",
                "m=audio 9 UDP/TLS/RTP/SAVPF 111",
                "a=rtpmap:111 opus/48000/2",
                "a=candidate:1 1 UDP 2122252543 10.0.0.1 54400 typ host",
            ]
        )

        info = connector.inspect_sdp(sdp)
        chunk = await connector.extract_audio_track(b"frame", sdp=sdp, timestamp_ms=200)

        assert info["has_audio"] is True
        assert info["audio_tracks"] == 1
        assert info["codec"] == "opus"
        assert info["ice_passthrough"] == info["ice_candidates"]
        assert chunk.format == "opus"
        assert chunks == [chunk]


class TestWebSocketConnector:
    @pytest.mark.asyncio
    async def test_websocket_connector_receives_streaming_audio_chunks(self, delivered_chunks):
        chunks, callback = delivered_chunks
        connector = WebSocketConnector(callback)
        await connector.start()

        chunk = await connector.receive_frame(
            b"\x00\x01\x02\x03",
            headers={"content-type": "audio/pcm"},
            timestamp_ms=300,
        )

        assert chunk.format == "pcm"
        assert chunk.sequence == 1
        assert chunks == [chunk]

    @pytest.mark.asyncio
    async def test_websocket_connector_handles_fragmentation_ordering(self, delivered_chunks):
        chunks, callback = delivered_chunks
        connector = WebSocketConnector(callback)

        first = await connector.receive_fragment("stream-1", b"world", index=2, final=False)
        final = await connector.receive_fragment(
            "stream-1",
            b"hello ",
            index=1,
            final=True,
            headers={"content-type": "audio/pcm"},
            timestamp_ms=400,
        )

        assert first is None
        assert final is not None
        assert final.data == b"hello world"
        assert chunks == [final]


class TestGRPCConnector:
    @pytest.mark.asyncio
    async def test_grpc_connector_sets_up_bidirectional_audio_stream(self, delivered_chunks):
        chunks, callback = delivered_chunks
        connector = GRPCConnector(callback)
        await connector.start()

        async def requests():
            yield {"audio": b"one", "headers": {"content-type": "audio/pcm"}, "timestamp_ms": 1}
            yield {"audio": b"two", "headers": {"content-type": "audio/wav"}, "timestamp_ms": 2}

        streamed = [chunk async for chunk in connector.bidirectional_stream(requests())]

        assert [chunk.data for chunk in streamed] == [b"one", b"two"]
        assert [chunk.format for chunk in streamed] == ["pcm", "wav"]
        assert chunks == streamed

    @pytest.mark.asyncio
    async def test_grpc_connector_streaming_recognition_pattern(self, delivered_chunks):
        _, callback = delivered_chunks
        connector = GRPCConnector(callback)

        async def requests():
            yield {"audio": b"hi", "headers": {"content-type": "audio/pcm"}, "timestamp_ms": 1}

        async def stt_callback(chunk: AudioChunk) -> str:
            return f"text:{chunk.sequence}"

        result = [text async for text in connector.recognize_streaming(requests(), stt_callback)]
        assert result == ["text:1"]

    def test_grpc_length_prefixed_audio_helpers(self, delivered_chunks):
        _, callback = delivered_chunks
        connector = GRPCConnector(callback)
        message = connector.make_length_prefixed_message(b"audio")
        assert connector.parse_length_prefixed_message(message) == b"audio"


@pytest.mark.asyncio
async def test_connector_timeout_and_reconnection_handling(delivered_chunks):
    _, callback = delivered_chunks
    connector = WebSocketConnector(callback, VoiceConfig(connector_timeout_s=1))

    await connector.start()
    await connector.handle_timeout()
    assert connector.running is False
    assert connector.reconnect_attempts == 1

    await connector.reconnect()
    assert connector.running is True
    assert connector.reconnect_attempts == 2
