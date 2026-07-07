"""Transcript-to-audio timeline mapping for voice sanitization."""

from __future__ import annotations

from typing import Any


class TimelineMapper:
    """Map detected transcript spans to millisecond audio frame ranges."""

    def __init__(self, sample_rate: int = 16000, safety_margin_ms: int = 50) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if safety_margin_ms < 0:
            raise ValueError("safety_margin_ms must be non-negative")
        self.sample_rate = sample_rate
        self.safety_margin_ms = safety_margin_ms

    def char_offset_to_ms(
        self,
        char_offset: int,
        text_start_ms: int,
        text_duration_ms: int,
        text_length: int,
    ) -> int:
        """Approximate a transcript character offset as an audio timestamp."""

        if text_length <= 0 or text_duration_ms <= 0:
            return text_start_ms
        bounded_offset = min(max(char_offset, 0), text_length)
        return text_start_ms + int((bounded_offset / text_length) * text_duration_ms)

    def entity_to_frame_range(
        self,
        entity: dict[str, Any],
        text_start_ms: int,
        text_duration_ms: int,
        text_length: int,
    ) -> tuple[int, int]:
        """Return a conservative audio range for one entity span."""

        start_offset = int(entity.get("start", entity.get("start_char", 0)))
        end_offset = int(entity.get("end", entity.get("end_char", start_offset)))
        start_ms = self.char_offset_to_ms(
            start_offset,
            text_start_ms,
            text_duration_ms,
            text_length,
        )
        end_ms = self.char_offset_to_ms(
            end_offset,
            text_start_ms,
            text_duration_ms,
            text_length,
        )
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        return (
            max(text_start_ms, start_ms - self.safety_margin_ms),
            min(text_start_ms + text_duration_ms, end_ms + self.safety_margin_ms),
        )

