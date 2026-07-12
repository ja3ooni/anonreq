"""Local-only speech-to-text engine for voice stream transcription."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from anonreq.voice.config import VoiceConfig
from anonreq.voice.connectors import AudioChunk
from anonreq.voice.transcript_buffer import TranscriptBuffer

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TranscriptionSegment:
    text: str
    timestamp_ms: int
    sequence: int


ModelFactory = Callable[[str, str], Any]


class STTEngine:
    """Local Whisper-compatible STT wrapper with streaming transcript buffering."""

    def __init__(
        self,
        config: VoiceConfig | None = None,
        model_factory: ModelFactory | None = None,
        eager_load: bool = False,
    ) -> None:
        self.config = config or VoiceConfig()
        self.device = self._select_device(self.config.stt_device)
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.transcript_buffer = TranscriptBuffer(
            max_chunks=self.config.transcript_buffer_max_chunks,
            window_ms=self.config.sliding_window_ms,
            overlap_ms=self.config.window_overlap_ms,
        )
        self._model_factory = model_factory
        self._model: Any | None = None
        self._load_lock = asyncio.Lock()
        self._closed = False
        if eager_load:
            self._model = self._load_model_sync()

    async def transcribe(self, audio: AudioChunk) -> str:
        """Transcribe one in-memory audio chunk using a local model only."""

        self._ensure_open()
        model = await self._load_model()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: self._run_model(model, audio))
        text = self._extract_text(result)
        if text:
            await self.transcript_buffer.add_chunk(text, audio.timestamp_ms)
        return text

    async def transcribe_streaming(
        self,
        chunks: AsyncIterator[AudioChunk],
    ) -> AsyncIterator[str]:
        async for chunk in chunks:
            text = await self.transcribe(chunk)
            if text:
                yield self.transcript_buffer.assemble_contiguous()

    async def close(self) -> None:
        self._closed = True
        self._model = None
        if self.device == "cuda":
            with contextlib.suppress(Exception):
                import torch

                torch.cuda.empty_cache()

    async def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:
                loop = asyncio.get_running_loop()
                self._model = await loop.run_in_executor(None, self._load_model_sync)
        return self._model

    def _load_model_sync(self) -> Any:
        if self._model_factory is not None:
            return self._model_factory(self.config.stt_model_size, self.device)
        try:
            from faster_whisper import WhisperModel

            return WhisperModel(
                self.config.stt_model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except ImportError:
            import whisper

            return whisper.load_model(self.config.stt_model_size, device=self.device)

    def _run_model(self, model: Any, audio: AudioChunk) -> Any:
        audio_input = self._audio_to_model_input(audio)
        if hasattr(model, "transcribe"):
            try:
                return model.transcribe(audio_input, language=None)
            except TypeError:
                return model.transcribe(audio_input)
        if callable(model):
            return model(audio_input)
        raise RuntimeError("STT model does not expose transcribe()")

    def _audio_to_model_input(self, audio: AudioChunk) -> Any:
        if audio.metadata.get("decoded_samples") is not None:
            return audio.metadata["decoded_samples"]
        if audio.format == "pcm":
            return self._pcm16le_to_float(audio.data)
        if audio.format == "wav":
            return audio.data
        if audio.format == "opus":
            return audio.data
        return audio.data

    @staticmethod
    def _pcm16le_to_float(data: bytes) -> list[float]:
        if len(data) < 2:
            return []
        sample_count = len(data) // 2
        return [
            int.from_bytes(data[index * 2 : index * 2 + 2], "little", signed=True) / 32768.0
            for index in range(sample_count)
        ]

    @staticmethod
    def _extract_text(result: Any) -> str:
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        if isinstance(result, tuple) and result:
            segments = result[0]
            return " ".join(str(getattr(segment, "text", segment)).strip() for segment in segments).strip()  # noqa: E501
        if isinstance(result, list):
            return " ".join(str(getattr(segment, "text", segment)).strip() for segment in result).strip()  # noqa: E501
        return str(getattr(result, "text", result or "")).strip()

    @staticmethod
    def _select_device(configured: str) -> str:
        if configured != "auto":
            return configured
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("STTEngine is closed")
