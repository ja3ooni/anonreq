from dataclasses import dataclass
import math
import re
from typing import Any, List

import numpy as np
import structlog

from anonreq.voice.config import VoiceConfig

logger = structlog.get_logger(__name__)

@dataclass
class DetectionTimestamp:
    start_ms: int
    end_ms: int
    entity_type: str

class AudioSanitizer:
    """Sanitize PCM audio streams by muting or masking sensitive ranges."""

    bytes_per_sample = 2

    def __init__(
        self,
        config: VoiceConfig | None = None,
        sample_rate: int | None = None,
        mode: str = "beep",
    ):
        self.config = config or VoiceConfig()
        self.sample_rate = sample_rate or self.config.audio_sample_rate
        self.mode = mode
        self._beep_frequency = 1000.0
        
    def _generate_beep(self, length_samples: int) -> np.ndarray:
        """Generate a 1kHz sine wave beep."""
        t = np.arange(length_samples) / self.sample_rate
        beep = np.sin(2 * np.pi * self._beep_frequency * t)
        # Apply a simple envelope to avoid clicks
        fade_samples = min(int(0.01 * self.sample_rate), length_samples // 2)
        if fade_samples > 0:
            envelope = np.ones(length_samples)
            fade = np.linspace(0, 1, fade_samples)
            envelope[:fade_samples] = fade
            envelope[-fade_samples:] = fade[::-1]
            beep = beep * envelope
        return beep.astype(np.float32)
        
    async def mute_frame(self, audio_data: bytes, sample_rate: int, start_ms: int, end_ms: int) -> bytes:
        """Replace PCM samples in the requested range with silence."""

        start_byte, end_byte = self._range_to_bytes(audio_data, sample_rate, start_ms, end_ms)
        if start_byte >= end_byte:
            return audio_data
        sanitized = bytearray(audio_data)
        sanitized[start_byte:end_byte] = b"\x00" * (end_byte - start_byte)
        return bytes(sanitized)

    async def beep_frame(
        self,
        audio_data: bytes,
        sample_rate: int,
        start_ms: int,
        end_ms: int,
        frequency: int = 1000,
        amplitude: float = 0.5,
    ) -> bytes:
        """Overlay a sine-wave mask over the requested PCM sample range."""

        start_byte, end_byte = self._range_to_bytes(audio_data, sample_rate, start_ms, end_ms)
        if start_byte >= end_byte:
            return audio_data
        sanitized = bytearray(audio_data)
        sample_count = (end_byte - start_byte) // self.bytes_per_sample
        amplitude = min(max(amplitude, 0.0), 1.0)
        for sample_index in range(sample_count):
            sample = int(32767 * amplitude * math.sin(2 * math.pi * frequency * sample_index / sample_rate))
            offset = start_byte + sample_index * self.bytes_per_sample
            sanitized[offset : offset + self.bytes_per_sample] = sample.to_bytes(
                self.bytes_per_sample,
                "little",
                signed=True,
            )
        return bytes(sanitized)

    async def sanitize(
        self,
        audio_data: bytes,
        entities: list[dict[str, Any]],
        method: str = "mute",
        sample_rate: int = 16000,
    ) -> bytes:
        """Apply muting or beeping to all entity frame ranges."""

        sanitized = audio_data
        for start_ms, end_ms in self._merge_ranges(entities):
            if method == "beep":
                sanitized = await self.beep_frame(sanitized, sample_rate, start_ms, end_ms)
            else:
                sanitized = await self.mute_frame(sanitized, sample_rate, start_ms, end_ms)
        return sanitized

    def sanitize_chunk(
        self, 
        audio_chunk: np.ndarray, 
        chunk_start_ms: int,
        detections: List[DetectionTimestamp]
    ) -> np.ndarray:
        """Sanitize an audio chunk based on detection timestamps.
        
        Args:
            audio_chunk: Numpy array of audio data.
            chunk_start_ms: Start time of this chunk in milliseconds.
            detections: List of sensitive entities detected.
            
        Returns:
            Sanitized audio chunk.
        """
        sanitized = audio_chunk.copy()
        chunk_duration_ms = (len(audio_chunk) / self.sample_rate) * 1000
        chunk_end_ms = chunk_start_ms + chunk_duration_ms
        
        for det in detections:
            # Check for overlap
            if det.end_ms <= chunk_start_ms or det.start_ms >= chunk_end_ms:
                continue
                
            # Calculate overlapping segment in ms relative to chunk
            overlap_start_ms = max(0, det.start_ms - chunk_start_ms)
            overlap_end_ms = min(chunk_duration_ms, det.end_ms - chunk_start_ms)
            
            # Convert to sample indices
            start_idx = int((overlap_start_ms / 1000.0) * self.sample_rate)
            end_idx = int((overlap_end_ms / 1000.0) * self.sample_rate)
            
            if start_idx >= end_idx:
                continue
                
            length_samples = end_idx - start_idx
            
            if self.mode == "beep":
                sanitized[start_idx:end_idx] = self._generate_beep(length_samples)
            else:
                # Mute
                sanitized[start_idx:end_idx] = 0.0
                
            logger.debug(
                f"Sanitized audio interval {overlap_start_ms}ms to {overlap_end_ms}ms",
                entity=det.entity_type,
                mode=self.mode
            )
            
        return sanitized

    def _range_to_bytes(
        self,
        audio_data: bytes,
        sample_rate: int,
        start_ms: int,
        end_ms: int,
    ) -> tuple[int, int]:
        sample_count = len(audio_data) // self.bytes_per_sample
        start_sample = max(0, min(sample_count, int(start_ms * sample_rate / 1000)))
        end_sample = max(start_sample, min(sample_count, int(end_ms * sample_rate / 1000)))
        return start_sample * self.bytes_per_sample, end_sample * self.bytes_per_sample

    @staticmethod
    def _merge_ranges(entities: list[dict[str, Any]]) -> list[tuple[int, int]]:
        ranges = sorted(
            (
                int(entity.get("audio_start_ms", entity.get("start_ms", 0))),
                int(entity.get("audio_end_ms", entity.get("end_ms", 0))),
            )
            for entity in entities
            if int(entity.get("audio_end_ms", entity.get("end_ms", 0)))
            > int(entity.get("audio_start_ms", entity.get("start_ms", 0)))
        )
        merged: list[tuple[int, int]] = []
        for start_ms, end_ms in ranges:
            if not merged or start_ms > merged[-1][1]:
                merged.append((start_ms, end_ms))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end_ms))
        return merged


class TextSanitizer:
    """Tokenize sensitive spans in transcript text using [TYPE_N] placeholders."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    async def sanitize_text(self, text: str, entities: list[dict[str, Any]]) -> str:
        sanitized = text
        replacements: list[tuple[int, int, str]] = []
        for entity in sorted(entities, key=lambda item: int(item.get("start", 0))):
            start = int(entity.get("start", 0))
            end = int(entity.get("end", start))
            if end <= start:
                continue
            entity_type = self._normalize_type(str(entity.get("entity_type", "PII")))
            self._counters[entity_type] = self._counters.get(entity_type, 0) + 1
            replacements.append((start, end, f"[{entity_type}_{self._counters[entity_type]}]"))
        for start, end, token in sorted(replacements, key=lambda item: item[0], reverse=True):
            sanitized = sanitized[:start] + token + sanitized[end:]
        return sanitized

    @staticmethod
    def _normalize_type(entity_type: str) -> str:
        normalized = re.sub(r"[^A-Za-z]", "", entity_type.upper())[:20]
        return normalized or "PII"
