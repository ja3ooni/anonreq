from __future__ import annotations

from dataclasses import dataclass

import pytest

from anonreq.voice.config import VoiceConfig
from anonreq.voice.connectors import AudioChunk
from anonreq.voice.stt_engine import STTEngine


@dataclass
class Segment:
    text: str


class FakeWhisperModel:
    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = texts or ["hello world"]
        self.calls = 0
        self.inputs = []

    def transcribe(self, audio):
        self.calls += 1
        self.inputs.append(audio)
        text = self.texts[min(self.calls - 1, len(self.texts) - 1)]
        return {"text": text}


def make_chunk(data: bytes = b"\x00\x00\xff\x7f", timestamp_ms: int = 0, sequence: int = 1) -> AudioChunk:
    return AudioChunk(data=data, format="pcm", timestamp_ms=timestamp_ms, sequence=sequence)


@pytest.mark.asyncio
async def test_stt_engine_transcribe_returns_text_from_audio_chunk():
    fake = FakeWhisperModel(["hello local"])
    engine = STTEngine(model_factory=lambda model_size, device: fake)

    text = await engine.transcribe(make_chunk())

    assert text == "hello local"
    assert fake.calls == 1
    assert engine.transcript_buffer.assemble_contiguous() == "hello local"


@pytest.mark.asyncio
async def test_stt_engine_streaming_transcription_assembles_overlapping_segments():
    fake = FakeWhisperModel(["hello world", "world again", "again soon"])
    engine = STTEngine(model_factory=lambda model_size, device: fake)

    async def chunks():
        yield make_chunk(timestamp_ms=0, sequence=1)
        yield make_chunk(timestamp_ms=250, sequence=2)
        yield make_chunk(timestamp_ms=500, sequence=3)

    result = [text async for text in engine.transcribe_streaming(chunks())]

    assert result == ["hello world", "hello world again", "hello world again soon"]


def test_stt_engine_uses_configurable_model_size_and_cpu_fallback(monkeypatch):
    monkeypatch.setattr("torch.cuda.is_available", lambda: False)
    seen: dict[str, str] = {}

    def factory(model_size: str, device: str):
        seen["model_size"] = model_size
        seen["device"] = device
        return FakeWhisperModel()

    engine = STTEngine(VoiceConfig(stt_model_size="small", stt_device="auto"), model_factory=factory, eager_load=True)

    assert engine.device == "cpu"
    assert seen == {"model_size": "small", "device": "cpu"}


def test_stt_engine_uses_cuda_when_available(monkeypatch):
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    engine = STTEngine(VoiceConfig(stt_device="auto"), model_factory=lambda _m, _d: FakeWhisperModel())

    assert engine.device == "cuda"
    assert engine.compute_type == "float16"


@pytest.mark.asyncio
async def test_stt_engine_close_unloads_model_and_rejects_future_use():
    engine = STTEngine(model_factory=lambda _m, _d: FakeWhisperModel(), eager_load=True)

    await engine.close()

    with pytest.raises(RuntimeError):
        await engine.transcribe(make_chunk())


@pytest.mark.asyncio
async def test_stt_engine_does_not_write_audio_to_disk(monkeypatch, tmp_path):
    writes: list[str] = []

    def forbidden_open(*args, **kwargs):
        writes.append(str(args[0]))
        raise AssertionError("disk write attempted")

    monkeypatch.setattr("builtins.open", forbidden_open)
    fake = FakeWhisperModel(["in memory"])
    engine = STTEngine(model_factory=lambda _m, _d: fake)

    assert await engine.transcribe(make_chunk()) == "in memory"
    assert writes == []

def test_stt_engine_extracts_faster_whisper_segments():
    assert STTEngine._extract_text(([Segment("hello"), Segment("world")], None)) == "hello world"

