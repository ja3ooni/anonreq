"""Configuration for voice and meeting stream protection."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AudioFormat = Literal["pcm", "wav", "opus"]


class VoiceConfig(BaseModel):
    """Runtime parameters for local voice ingestion and transcription."""

    SUPPORTED_MODEL_SIZES: ClassVar[set[str]] = {"tiny", "base", "small", "medium", "large"}
    SUPPORTED_DEVICES: ClassVar[set[str]] = {"auto", "cuda", "cpu"}
    SUPPORTED_AUDIO_FORMATS: ClassVar[tuple[str, ...]] = ("pcm", "wav", "opus")

    stt_model_size: str = "base"
    stt_device: str = "auto"
    audio_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    sliding_window_ms: int = Field(default=500, gt=0)
    window_overlap_ms: int = Field(default=125, ge=0)
    transcript_buffer_max_chunks: int = Field(default=100, gt=0)
    latency_budget_ms: int = Field(default=150, gt=0)
    connector_timeout_s: int = Field(default=30, gt=0)
    max_connections: int = Field(default=100, gt=0)

    @field_validator("stt_model_size")
    @classmethod
    def _validate_model_size(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in cls.SUPPORTED_MODEL_SIZES:
            allowed = ", ".join(sorted(cls.SUPPORTED_MODEL_SIZES))
            raise ValueError(f"stt_model_size must be one of: {allowed}")
        return normalized

    @field_validator("stt_device")
    @classmethod
    def _validate_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in cls.SUPPORTED_DEVICES:
            allowed = ", ".join(sorted(cls.SUPPORTED_DEVICES))
            raise ValueError(f"stt_device must be one of: {allowed}")
        return normalized

    @model_validator(mode="after")
    def _validate_window_overlap(self) -> VoiceConfig:
        if self.window_overlap_ms >= self.sliding_window_ms:
            raise ValueError("window_overlap_ms must be smaller than sliding_window_ms")
        if self.sliding_window_ms > self.latency_budget_ms and self.latency_budget_ms < 150:
            raise ValueError("latency_budget_ms must preserve the 150ms P99 budget")
        return self

    @property
    def supported_audio_formats(self) -> tuple[str, ...]:
        return self.SUPPORTED_AUDIO_FORMATS

