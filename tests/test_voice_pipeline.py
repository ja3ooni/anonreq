from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from anonreq.voice.config import VoiceConfig
from anonreq.voice.connectors import AudioChunk
from anonreq.voice.detector import SlidingWindowDetector
from anonreq.voice.pipeline import VoicePipeline
from anonreq.voice.sanitizer import AudioSanitizer, TextSanitizer
from anonreq.voice.timeline import TimelineMapper


class FakeSTT:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)

    async def transcribe(self, _chunk: AudioChunk) -> str:
        return self.outputs.pop(0)


class FakeDetectionEngine:
    async def detect(self, text: str):
        start = text.find("john@example.com")
        if start < 0:
            return []
        return [
            {
                "start": start,
                "end": start + len("john@example.com"),
                "entity_type": "EMAIL",
                "text": "john@example.com",
                "score": 0.99,
            }
        ]


class FakeConnector:
    def __init__(self, chunks: list[AudioChunk]) -> None:
        self.chunks = chunks
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def stream_chunks(self) -> AsyncIterator[AudioChunk]:
        for chunk in self.chunks:
            yield chunk


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def log_event(self, event_type: str, **fields) -> None:
        self.events.append((event_type, fields))


def make_chunk(timestamp_ms: int = 0) -> AudioChunk:
    return AudioChunk(
        data=(1000).to_bytes(2, "little", signed=True) * 8000,
        format="pcm",
        timestamp_ms=timestamp_ms,
        sequence=1,
        sample_rate=16000,
    )


@pytest.mark.asyncio
async def test_voice_pipeline_orchestrates_audio_sanitization_flow():
    config = VoiceConfig(sliding_window_ms=500, window_overlap_ms=125)
    detector = SlidingWindowDetector(FakeDetectionEngine(), TimelineMapper(), 500, 125)
    audit = FakeAudit()
    pipeline = VoicePipeline(
        stt_engine=FakeSTT(["email john@example.com"]),
        detector=detector,
        audio_sanitizer=AudioSanitizer(config),
        text_sanitizer=TextSanitizer(),
        config=config,
        audit_logger=audit,
    )
    connector = FakeConnector([make_chunk()])

    output = [chunk async for chunk in pipeline.process_stream(connector, output_format="audio", method="mute")]  # noqa: E501

    assert connector.started is True
    assert connector.stopped is True
    assert len(output) == 1
    assert isinstance(output[0], bytes)
    assert output[0] != make_chunk().data
    assert ("voice_stream_started", {}) in [(event, {}) for event, _ in audit.events]
    assert any(event == "voice_entity_detected" for event, _ in audit.events)
    assert any(event == "voice_audio_sanitized" for event, _ in audit.events)
    assert any(event == "voice_stream_ended" for event, _ in audit.events)


@pytest.mark.asyncio
async def test_voice_pipeline_text_output_path_tokenizes_sensitive_spans():
    config = VoiceConfig()
    detector = SlidingWindowDetector(FakeDetectionEngine(), TimelineMapper(), 500, 125)
    pipeline = VoicePipeline(
        stt_engine=FakeSTT(["email john@example.com"]),
        detector=detector,
        audio_sanitizer=AudioSanitizer(config),
        text_sanitizer=TextSanitizer(),
        config=config,
    )

    output = [
        text
        async for text in pipeline.process_stream(
            FakeConnector([make_chunk()]),
            output_format="text",
        )
    ]

    assert output == ["email [EMAIL_1]"]


@pytest.mark.asyncio
async def test_voice_pipeline_preserves_sequence_order_for_sanitized_frames():
    config = VoiceConfig()
    detector = SlidingWindowDetector(FakeDetectionEngine(), TimelineMapper(), 500, 125)
    pipeline = VoicePipeline(
        stt_engine=FakeSTT(["email john@example.com", "no pii here"]),
        detector=detector,
        audio_sanitizer=AudioSanitizer(config),
        text_sanitizer=TextSanitizer(),
        config=config,
    )
    first = make_chunk(timestamp_ms=0)
    second = AudioChunk(
        data=b"\x01\x00" * 8000,
        format="pcm",
        timestamp_ms=500,
        sequence=2,
        sample_rate=16000,
    )

    output = [
        frame async for frame in pipeline.process_stream(FakeConnector([first, second]), output_format="audio")  # noqa: E501
    ]

    assert len(output) == 2
    assert output[0] != first.data
    assert output[1] == second.data


@pytest.mark.asyncio
async def test_voice_pipeline_records_latency_exceeded_event():
    config = VoiceConfig()
    config.latency_budget_ms = 1
    detector = SlidingWindowDetector(FakeDetectionEngine(), TimelineMapper(), 500, 125)
    audit = FakeAudit()
    pipeline = VoicePipeline(
        stt_engine=FakeSTT(["email john@example.com"]),
        detector=detector,
        audio_sanitizer=AudioSanitizer(config),
        text_sanitizer=TextSanitizer(),
        config=config,
        audit_logger=audit,
        clock=lambda: 0.0,
    )
    times = iter([0.0, 0.01])
    pipeline._clock = lambda: next(times)

    _ = [frame async for frame in pipeline.process_stream(FakeConnector([make_chunk()]), output_format="audio")]  # noqa: E501

    assert any(event == "voice_latency_exceeded" for event, _ in audit.events)
