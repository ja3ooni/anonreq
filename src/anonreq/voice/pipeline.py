"""Voice pipeline orchestration from audio chunks to sanitized outputs."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog

from anonreq.voice.config import VoiceConfig
from anonreq.voice.connectors import AudioChunk, BaseConnector
from anonreq.voice.detector import SlidingWindowDetector
from anonreq.voice.metrics import (
    voice_audio_sanitized_seconds_total,
    voice_entities_detected_total,
    voice_latency_exceeded_total,
    voice_latency_ms,
    voice_streams_active,
)
from anonreq.voice.sanitizer import AudioSanitizer, TextSanitizer
from anonreq.voice.stt_engine import STTEngine


log = structlog.get_logger(__name__)


class VoicePipeline:
    """Orchestrate STT, sliding-window detection, and audio/text sanitization."""

    def __init__(
        self,
        stt_engine: STTEngine,
        detector: SlidingWindowDetector,
        audio_sanitizer: AudioSanitizer,
        text_sanitizer: TextSanitizer,
        config: VoiceConfig | None = None,
        audit_logger: Any | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.stt_engine = stt_engine
        self.detector = detector
        self.audio_sanitizer = audio_sanitizer
        self.text_sanitizer = text_sanitizer
        self.config = config or VoiceConfig()
        self.audit_logger = audit_logger
        self._clock = clock or time.perf_counter
        self.running = False

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False

    async def process_stream(
        self,
        connector: BaseConnector,
        output_format: str = "audio",
        method: str = "mute",
    ) -> AsyncIterator[bytes | str]:
        """Process a finite connector stream and yield sanitized frames or text."""

        await self.start()
        await self._emit_audit("voice_stream_started")
        connector_type = self._connector_type(connector)
        tenant_id = "default"
        voice_streams_active.labels(connector_type=connector_type, tenant_id=tenant_id).inc()
        try:
            if hasattr(connector, "start"):
                await connector.start()
            async for chunk in self._iter_connector_chunks(connector):
                started = self._clock()
                text = await self.stt_engine.transcribe(chunk)
                entities = await self.detector.process_chunk(
                    text,
                    audio_start_ms=chunk.timestamp_ms,
                    audio_duration_ms=self._chunk_duration_ms(chunk),
                )
                if entities:
                    for entity in entities:
                        voice_entities_detected_total.labels(
                            entity_type=str(entity.get("entity_type", "unknown")).lower(),
                            connector_type=connector_type,
                        ).inc()
                    await self._emit_audit(
                        "voice_entity_detected",
                        entity_count=len(entities),
                        entity_types=sorted({entity["entity_type"] for entity in entities}),
                    )
                if output_format == "text":
                    output: bytes | str = await self.text_sanitizer.sanitize_text(text, entities)
                else:
                    output = await self.audio_sanitizer.sanitize(
                        chunk.data,
                        entities,
                        method=method,
                        sample_rate=chunk.sample_rate,
                    )
                    if entities:
                        duration_s = sum(
                            max(
                                0,
                                int(entity.get("audio_end_ms", entity.get("end_ms", 0)))
                                - int(entity.get("audio_start_ms", entity.get("start_ms", 0))),
                            )
                            for entity in entities
                        ) / 1000.0
                        voice_audio_sanitized_seconds_total.labels(
                            method=method,
                            connector_type=connector_type,
                        ).inc(duration_s)
                        await self._emit_audit(
                            "voice_audio_sanitized",
                            entity_count=len(entities),
                            method=method,
                        )
                elapsed_ms = (self._clock() - started) * 1000
                voice_latency_ms.labels(connector_type=connector_type).observe(elapsed_ms)
                if elapsed_ms > self.config.latency_budget_ms:
                    voice_latency_exceeded_total.labels(connector_type=connector_type).inc()
                    await self._emit_audit(
                        "voice_latency_exceeded",
                        latency_ms=round(elapsed_ms, 3),
                        budget_ms=self.config.latency_budget_ms,
                    )
                yield output
        finally:
            with _suppress_exceptions():
                if hasattr(connector, "stop"):
                    await connector.stop()
            voice_streams_active.labels(connector_type=connector_type, tenant_id=tenant_id).dec()
            await self._emit_audit("voice_stream_ended")
            await self.stop()

    async def _iter_connector_chunks(self, connector: Any) -> AsyncIterator[AudioChunk]:
        if hasattr(connector, "stream_chunks"):
            async for chunk in connector.stream_chunks():
                yield chunk
            return
        if hasattr(connector, "chunks"):
            async for chunk in connector.chunks():
                yield chunk
            return
        raise RuntimeError("connector must expose stream_chunks() or chunks()")

    @staticmethod
    def _chunk_duration_ms(chunk: AudioChunk) -> int:
        if chunk.sample_rate <= 0:
            return 0
        if chunk.format != "pcm":
            return int(chunk.metadata.get("duration_ms", 0)) or 1
        samples = len(chunk.data) // 2
        return max(1, int(samples / chunk.sample_rate * 1000))

    @staticmethod
    def _connector_type(connector: Any) -> str:
        return str(getattr(connector, "connector_name", connector.__class__.__name__)).lower()

    async def _emit_audit(self, event_type: str, **fields: Any) -> None:
        safe_fields = {key: value for key, value in fields.items() if key not in {"text", "audio", "content"}}
        if self.audit_logger is None:
            log.info(event_type, **safe_fields)
            return
        if hasattr(self.audit_logger, "log_event"):
            result = self.audit_logger.log_event(event_type, **safe_fields)
        elif hasattr(self.audit_logger, "info"):
            result = self.audit_logger.info(event_type, **safe_fields)
        else:
            return
        if hasattr(result, "__await__"):
            await result


class _suppress_exceptions:
    def __enter__(self) -> None:
        return None

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
        return True
