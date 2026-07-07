"""Voice channel connectors for SIP, WebRTC, WebSocket, and gRPC streams."""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import struct
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from anonreq.voice.config import VoiceConfig


log = structlog.get_logger(__name__)

AudioCallback = Callable[["AudioChunk"], Awaitable[None]]


@dataclass(frozen=True)
class AudioChunk:
    """In-memory audio payload extracted from a voice channel."""

    data: bytes
    format: str
    timestamp_ms: int
    sequence: int
    sample_rate: int = 16000
    channels: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """Common lifecycle and chunk delivery behavior for voice connectors."""

    connector_name = "base"

    def __init__(
        self,
        audio_callback: AudioCallback,
        config: VoiceConfig | None = None,
    ) -> None:
        self.audio_callback = audio_callback
        self.config = config or VoiceConfig()
        self.running = False
        self.reconnect_attempts = 0
        self._sequence = itertools.count(1)
        self._active_connections = 0
        self._last_activity_ms: int | None = None

    @abstractmethod
    async def start(self) -> None:
        """Start accepting or inspecting a voice channel."""

    async def stop(self) -> None:
        self.running = False
        self._active_connections = 0

    async def deliver_audio(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        timestamp_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AudioChunk:
        """Detect format, create an AudioChunk, and deliver it to STT callback."""

        fmt = self.detect_audio_format(headers or {}, data)
        chunk = AudioChunk(
            data=data,
            format=fmt,
            timestamp_ms=timestamp_ms if timestamp_ms is not None else self._now_ms(),
            sequence=next(self._sequence),
            sample_rate=self.config.audio_sample_rate,
            metadata={"connector": self.connector_name, **(metadata or {})},
        )
        await asyncio.wait_for(self.audio_callback(chunk), timeout=self.config.connector_timeout_s)
        self._last_activity_ms = chunk.timestamp_ms
        return chunk

    async def handle_timeout(self) -> None:
        """Record a reconnect attempt after an idle timeout."""

        self.reconnect_attempts += 1
        self.running = False
        log.warning(
            "voice.connector.timeout",
            connector=self.connector_name,
            reconnect_attempts=self.reconnect_attempts,
        )

    async def reconnect(self) -> None:
        self.reconnect_attempts += 1
        await self.start()

    def can_accept_connection(self) -> bool:
        return self._active_connections < self.config.max_connections

    @classmethod
    def detect_audio_format(cls, headers: dict[str, str], data: bytes) -> str:
        normalized = {key.lower(): value.lower() for key, value in headers.items()}
        content_type = normalized.get("content-type", "")
        codec = normalized.get("codec", "") or normalized.get("rtpmap", "")

        if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
            return "wav"
        if "wav" in content_type or "wave" in content_type:
            return "wav"
        if "opus" in content_type or "opus" in codec:
            return "opus"
        if "pcm" in content_type or "l16" in content_type or "audio/raw" in content_type:
            return "pcm"
        if len(data) >= 2 and cls._looks_like_rtp_opus(data):
            return "opus"
        return "pcm"

    @staticmethod
    def _looks_like_rtp_opus(data: bytes) -> bool:
        if len(data) < 12:
            return False
        version = data[0] >> 6
        payload_type = data[1] & 0x7F
        return version == 2 and payload_type in {96, 97, 98, 111}

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)


class SIPConnector(BaseConnector):
    """SIP trunk proxy connector that inspects SIP and extracts RTP audio."""

    connector_name = "sip"

    async def start(self) -> None:
        if not self.can_accept_connection():
            raise RuntimeError("SIP connector connection limit exceeded")
        self.running = True
        self._active_connections += 1

    def inspect_sip_message(self, message: bytes) -> dict[str, Any]:
        text = message.decode("utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        is_invite = bool(lines and lines[0].upper().startswith("INVITE "))
        codec = "opus" if any("opus" in line.lower() for line in lines) else "pcm"
        media_ports = [
            int(parts[1])
            for line in lines
            if line.startswith("m=audio")
            for parts in [line.split()]
            if len(parts) > 1 and parts[1].isdigit()
        ]
        return {
            "is_invite": is_invite,
            "codec": codec,
            "media_ports": media_ports,
            "routing_headers_preserved": all(
                any(line.lower().startswith(header) for line in lines)
                for header in ("via:", "from:", "to:", "call-id:")
            ),
        }

    async def proxy_sip_message(self, message: bytes) -> dict[str, Any]:
        info = self.inspect_sip_message(message)
        info["forked"] = True
        return info

    async def extract_rtp_packet(self, packet: bytes, timestamp_ms: int | None = None) -> AudioChunk:
        payload = packet[12:] if len(packet) >= 12 and self._looks_like_rtp_opus(packet) else packet
        return await self.deliver_audio(
            payload,
            headers={"content-type": "audio/opus" if payload != packet else "audio/pcm"},
            timestamp_ms=timestamp_ms,
            metadata={"source": "rtp"},
        )


class WebRTCConnector(BaseConnector):
    """WebRTC media connector with SDP inspection and ICE passthrough."""

    connector_name = "webrtc"

    async def start(self) -> None:
        if not self.can_accept_connection():
            raise RuntimeError("WebRTC connector connection limit exceeded")
        self.running = True
        self._active_connections += 1

    def inspect_sdp(self, sdp: str) -> dict[str, Any]:
        lines = [line.strip() for line in sdp.splitlines() if line.strip()]
        audio_lines = [line for line in lines if line.startswith("m=audio")]
        ice_candidates = [line for line in lines if line.startswith("a=candidate:")]
        codec = "opus" if any("opus" in line.lower() for line in lines) else "pcm"
        return {
            "has_audio": bool(audio_lines),
            "audio_tracks": len(audio_lines),
            "codec": codec,
            "ice_candidates": ice_candidates,
            "ice_passthrough": list(ice_candidates),
        }

    async def extract_audio_track(
        self,
        frame: bytes,
        sdp: str | None = None,
        timestamp_ms: int | None = None,
    ) -> AudioChunk:
        codec = self.inspect_sdp(sdp or "").get("codec", "pcm")
        return await self.deliver_audio(
            frame,
            headers={"content-type": f"audio/{codec}"},
            timestamp_ms=timestamp_ms,
            metadata={"source": "webrtc"},
        )


class WebSocketConnector(BaseConnector):
    """WebSocket streaming connector for binary audio frames."""

    connector_name = "websocket"

    def __init__(self, audio_callback: AudioCallback, config: VoiceConfig | None = None) -> None:
        super().__init__(audio_callback, config)
        self._fragments: dict[str, list[tuple[int, bytes]]] = {}

    async def start(self) -> None:
        if not self.can_accept_connection():
            raise RuntimeError("WebSocket connector connection limit exceeded")
        self.running = True
        self._active_connections += 1

    async def receive_frame(
        self,
        frame: bytes,
        headers: dict[str, str] | None = None,
        timestamp_ms: int | None = None,
    ) -> AudioChunk:
        return await self.deliver_audio(frame, headers=headers, timestamp_ms=timestamp_ms, metadata={"source": "websocket"})

    async def receive_fragment(
        self,
        stream_id: str,
        fragment: bytes,
        index: int,
        final: bool,
        headers: dict[str, str] | None = None,
        timestamp_ms: int | None = None,
    ) -> AudioChunk | None:
        fragments = self._fragments.setdefault(stream_id, [])
        fragments.append((index, fragment))
        if not final:
            return None
        data = b"".join(part for _, part in sorted(fragments, key=lambda item: item[0]))
        self._fragments.pop(stream_id, None)
        return await self.receive_frame(data, headers=headers, timestamp_ms=timestamp_ms)


class GRPCConnector(BaseConnector):
    """Bidirectional gRPC-style audio stream connector."""

    connector_name = "grpc"

    async def start(self) -> None:
        if not self.can_accept_connection():
            raise RuntimeError("gRPC connector connection limit exceeded")
        self.running = True
        self._active_connections += 1

    async def bidirectional_stream(
        self,
        requests: AsyncIterator[bytes | dict[str, Any]],
    ) -> AsyncIterator[AudioChunk]:
        async for request in requests:
            if isinstance(request, dict):
                data = request.get("audio", b"")
                headers = request.get("headers", {})
                timestamp_ms = request.get("timestamp_ms")
            else:
                data = request
                headers = {"content-type": "audio/pcm"}
                timestamp_ms = None
            chunk = await self.deliver_audio(
                data,
                headers=headers,
                timestamp_ms=timestamp_ms,
                metadata={"source": "grpc"},
            )
            yield chunk

    async def recognize_streaming(
        self,
        requests: AsyncIterator[bytes | dict[str, Any]],
        stt_callback: Callable[[AudioChunk], Awaitable[str]],
    ) -> AsyncIterator[str]:
        async for chunk in self.bidirectional_stream(requests):
            text = await stt_callback(chunk)
            if text:
                yield text

    @staticmethod
    def make_length_prefixed_message(audio: bytes) -> bytes:
        return struct.pack(">I", len(audio)) + audio

    @staticmethod
    def parse_length_prefixed_message(message: bytes) -> bytes:
        if len(message) < 4:
            raise ValueError("gRPC audio message is missing length prefix")
        size = struct.unpack(">I", message[:4])[0]
        if len(message[4:]) != size:
            raise ValueError("gRPC audio message length mismatch")
        return message[4:]


async def collect_chunks(connector: BaseConnector, chunks: list[bytes]) -> list[AudioChunk]:
    """Test helper used by connector consumers to feed finite in-memory streams."""

    delivered: list[AudioChunk] = []

    async def capture(chunk: AudioChunk) -> None:
        delivered.append(chunk)

    original_callback = connector.audio_callback
    connector.audio_callback = capture
    try:
        for chunk in chunks:
            await connector.deliver_audio(chunk)
    finally:
        connector.audio_callback = original_callback
    return delivered


@contextlib.asynccontextmanager
async def running_connector(connector: BaseConnector) -> AsyncIterator[BaseConnector]:
    await connector.start()
    try:
        yield connector
    finally:
        await connector.stop()
