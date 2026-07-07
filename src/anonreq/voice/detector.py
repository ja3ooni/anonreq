"""Sliding-window PII detection for voice transcripts."""

from __future__ import annotations

import inspect
from collections import deque
from dataclasses import dataclass
from typing import Any

from anonreq.voice.timeline import TimelineMapper


@dataclass(frozen=True)
class TranscriptWindowSegment:
    text: str
    audio_start_ms: int
    audio_duration_ms: int
    sequence: int

    @property
    def audio_end_ms(self) -> int:
        return self.audio_start_ms + self.audio_duration_ms


class SlidingWindowDetector:
    """Detect sensitive transcript spans using overlapping audio windows."""

    def __init__(
        self,
        detection_engine: Any,
        timeline_mapper: TimelineMapper | None = None,
        window_ms: int = 500,
        overlap_ms: int = 125,
    ) -> None:
        if window_ms <= 0:
            raise ValueError("window_ms must be positive")
        if overlap_ms < 0 or overlap_ms >= window_ms:
            raise ValueError("overlap_ms must be non-negative and smaller than window_ms")
        self.detection_engine = detection_engine
        self.timeline_mapper = timeline_mapper or TimelineMapper()
        self.window_ms = window_ms
        self.overlap_ms = overlap_ms
        self._window_buffer: deque[TranscriptWindowSegment] = deque()
        self._sequence = 0
        self._pending_entities: list[dict[str, Any]] = []
        self._emitted_keys: set[tuple[str, int, int, str]] = set()

    async def process_chunk(
        self,
        text: str,
        audio_start_ms: int,
        audio_duration_ms: int,
    ) -> list[dict[str, Any]]:
        """Add one STT chunk and return newly detected timeline entities."""

        normalized = text or ""
        if normalized:
            self._sequence += 1
            self._window_buffer.append(
                TranscriptWindowSegment(
                    text=normalized,
                    audio_start_ms=audio_start_ms,
                    audio_duration_ms=audio_duration_ms,
                    sequence=self._sequence,
                )
            )
        if not self._window_buffer or self._current_duration_ms() < self.window_ms:
            return []

        window_text, offsets = self._assemble_window()
        raw_entities = await self._detect(window_text)
        entities = [
            mapped
            for raw_entity in raw_entities
            for mapped in [self._map_entity(raw_entity, window_text, offsets)]
            if mapped is not None and self._mark_new(mapped)
        ]
        self._pending_entities.extend(entities)
        self._prune_for_overlap()
        return entities

    def get_pending_entities(self) -> list[dict[str, Any]]:
        return list(self._pending_entities)

    def clear_pending(self) -> None:
        self._pending_entities.clear()

    def _current_duration_ms(self) -> int:
        if not self._window_buffer:
            return 0
        return self._window_buffer[-1].audio_end_ms - self._window_buffer[0].audio_start_ms

    def _assemble_window(self) -> tuple[str, list[tuple[int, int, TranscriptWindowSegment]]]:
        parts: list[str] = []
        offsets: list[tuple[int, int, TranscriptWindowSegment]] = []
        cursor = 0
        for segment in self._window_buffer:
            parts.append(segment.text)
            start = cursor
            cursor += len(segment.text)
            offsets.append((start, cursor, segment))
        return "".join(parts), offsets

    async def _detect(self, text: str) -> list[Any]:
        detector = getattr(self.detection_engine, "detect", self.detection_engine)
        result = detector(text)
        if inspect.isawaitable(result):
            result = await result
        return list(result or [])

    def _map_entity(
        self,
        raw_entity: Any,
        window_text: str,
        offsets: list[tuple[int, int, TranscriptWindowSegment]],
    ) -> dict[str, Any] | None:
        entity = self._entity_to_dict(raw_entity, window_text)
        start = int(entity.get("start", 0))
        end = int(entity.get("end", start))
        if end <= start:
            return None
        start_segment = self._segment_for_offset(start, offsets)
        end_segment = self._segment_for_offset(max(end - 1, start), offsets)
        if start_segment is None or end_segment is None:
            return None

        start_base, _, first_segment = start_segment
        end_base, _, last_segment = end_segment
        start_ms = self.timeline_mapper.entity_to_frame_range(
            {"start": start - start_base, "end": start - start_base + 1},
            first_segment.audio_start_ms,
            first_segment.audio_duration_ms,
            len(first_segment.text),
        )[0]
        end_ms = self.timeline_mapper.entity_to_frame_range(
            {"start": max(end - end_base - 1, 0), "end": end - end_base},
            last_segment.audio_start_ms,
            last_segment.audio_duration_ms,
            len(last_segment.text),
        )[1]
        entity.update(
            {
                "audio_start_ms": start_ms,
                "audio_end_ms": max(end_ms, start_ms + 1),
                "window_start_ms": self._window_buffer[0].audio_start_ms,
                "window_end_ms": self._window_buffer[-1].audio_end_ms,
            }
        )
        return entity

    @staticmethod
    def _entity_to_dict(raw_entity: Any, text: str) -> dict[str, Any]:
        if isinstance(raw_entity, dict):
            entity = dict(raw_entity)
        else:
            entity = {
                "start": getattr(raw_entity, "start", getattr(raw_entity, "start_char", 0)),
                "end": getattr(raw_entity, "end", getattr(raw_entity, "end_char", 0)),
                "entity_type": getattr(raw_entity, "entity_type", getattr(raw_entity, "type", "PII")),
                "score": getattr(raw_entity, "score", getattr(raw_entity, "confidence", None)),
            }
        if "start" not in entity and "start_char" in entity:
            entity["start"] = entity["start_char"]
        if "end" not in entity and "end_char" in entity:
            entity["end"] = entity["end_char"]
        entity["start"] = int(entity.get("start", 0))
        entity["end"] = int(entity.get("end", entity["start"]))
        entity["entity_type"] = str(entity.get("entity_type", entity.get("type", "PII"))).upper()
        entity.setdefault("text", text[entity["start"] : entity["end"]])
        return entity

    @staticmethod
    def _segment_for_offset(
        char_offset: int,
        offsets: list[tuple[int, int, TranscriptWindowSegment]],
    ) -> tuple[int, int, TranscriptWindowSegment] | None:
        for start, end, segment in offsets:
            if start <= char_offset < end:
                return start, end, segment
        return offsets[-1] if offsets else None

    def _mark_new(self, entity: dict[str, Any]) -> bool:
        key = (
            entity["entity_type"],
            int(entity["audio_start_ms"]),
            int(entity["audio_end_ms"]),
            str(entity.get("text", "")),
        )
        if key in self._emitted_keys:
            return False
        self._emitted_keys.add(key)
        return True

    def _prune_for_overlap(self) -> None:
        if not self._window_buffer:
            return
        keep_from_ms = self._window_buffer[-1].audio_end_ms - self.overlap_ms
        while len(self._window_buffer) > 1 and self._window_buffer[0].audio_end_ms <= keep_from_ms:
            self._window_buffer.popleft()

