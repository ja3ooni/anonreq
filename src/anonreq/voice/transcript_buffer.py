"""In-memory transcript buffer with sliding window assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    timestamp_ms: int
    sequence: int
    metadata: dict[str, Any] | None = None


class TranscriptBuffer:
    """Ring buffer for streaming transcript segments.

    The buffer keeps transcript text in process memory only. Segments are ordered
    by timestamp and sequence to make overlapping-window detection deterministic.
    """

    def __init__(self, max_chunks: int = 100, window_ms: int = 500, overlap_ms: int = 125) -> None:
        if max_chunks <= 0:
            raise ValueError("max_chunks must be positive")
        if window_ms <= 0:
            raise ValueError("window_ms must be positive")
        if overlap_ms < 0 or overlap_ms >= window_ms:
            raise ValueError("overlap_ms must be non-negative and smaller than window_ms")
        self.max_chunks = max_chunks
        self.window_ms = window_ms
        self.overlap_ms = overlap_ms
        self._segments: list[TranscriptSegment] = []
        self._next_sequence = 1

    async def add_chunk(self, text: str, timestamp_ms: int) -> None:
        normalized = text.strip()
        if not normalized:
            return
        segment = TranscriptSegment(
            text=normalized,
            timestamp_ms=timestamp_ms,
            sequence=self._next_sequence,
        )
        self._next_sequence += 1
        self._segments.append(segment)
        self._segments.sort(key=lambda item: (item.timestamp_ms, item.sequence))
        if len(self._segments) > self.max_chunks:
            del self._segments[: len(self._segments) - self.max_chunks]

    def get_window(self, timestamp_ms: int) -> list[dict[str, Any]]:
        start_ms = timestamp_ms - self.window_ms
        end_ms = timestamp_ms
        return [
            {
                "text": segment.text,
                "timestamp_ms": segment.timestamp_ms,
                "sequence": segment.sequence,
            }
            for segment in self._segments
            if start_ms <= segment.timestamp_ms <= end_ms
        ]

    def assemble_contiguous(self) -> str:
        parts: list[str] = []
        for segment in sorted(self._segments, key=lambda item: (item.timestamp_ms, item.sequence)):
            if not parts:
                parts.append(segment.text)
            else:
                parts.append(self._merge_overlap(parts[-1], segment.text))
        return " ".join(part for part in parts if part).strip()

    def clear_before(self, timestamp_ms: int) -> None:
        self._segments = [segment for segment in self._segments if segment.timestamp_ms >= timestamp_ms]  # noqa: E501

    def as_list(self) -> list[TranscriptSegment]:
        return list(self._segments)

    def __len__(self) -> int:
        return len(self._segments)

    @staticmethod
    def _merge_overlap(previous: str, current: str) -> str:
        previous_words = previous.split()
        current_words = current.split()
        max_overlap = min(len(previous_words), len(current_words))
        for size in range(max_overlap, 0, -1):
            if previous_words[-size:] == current_words[:size]:
                return " ".join(current_words[size:])
        return current
