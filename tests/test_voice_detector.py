from __future__ import annotations

import pytest

from anonreq.voice.detector import SlidingWindowDetector
from anonreq.voice.timeline import TimelineMapper


class FakeDetectionEngine:
    async def detect(self, text: str):
        results = []
        for value, entity_type in [
            ("john@example.com", "EMAIL"),
            ("Jane Doe", "PERSON"),
            ("555-1212", "PHONE"),
        ]:
            start = text.find(value)
            if start >= 0:
                results.append(
                    {
                        "start": start,
                        "end": start + len(value),
                        "entity_type": entity_type,
                        "score": 0.99,
                        "text": value,
                    }
                )
        return results


def test_timeline_mapper_converts_character_offsets_to_audio_offsets():
    mapper = TimelineMapper(sample_rate=16000)

    assert mapper.char_offset_to_ms(5, text_start_ms=1000, text_duration_ms=1000, text_length=10) == 1500  # noqa: E501

    frame_range = mapper.entity_to_frame_range(
        {"start": 5, "end": 10, "entity_type": "EMAIL"},
        text_start_ms=1000,
        text_duration_ms=1000,
        text_length=20,
    )

    assert frame_range == (1200, 1550)


@pytest.mark.asyncio
async def test_sliding_window_detector_buffers_until_window_duration():
    detector = SlidingWindowDetector(
        FakeDetectionEngine(),
        TimelineMapper(),
        window_ms=500,
        overlap_ms=125,
    )

    first = await detector.process_chunk("Call ", audio_start_ms=0, audio_duration_ms=200)
    second = await detector.process_chunk("Jane Doe at ", audio_start_ms=200, audio_duration_ms=200)
    third = await detector.process_chunk("555-1212", audio_start_ms=400, audio_duration_ms=200)

    assert first == []
    assert second == []
    assert [entity["entity_type"] for entity in third] == ["PERSON", "PHONE"]
    assert detector.get_pending_entities() == third


@pytest.mark.asyncio
async def test_entity_detected_in_text_maps_to_millisecond_audio_range():
    detector = SlidingWindowDetector(
        FakeDetectionEngine(),
        TimelineMapper(),
        window_ms=500,
        overlap_ms=125,
    )

    entities = await detector.process_chunk(
        "Email john@example.com now",
        audio_start_ms=1000,
        audio_duration_ms=500,
    )

    assert len(entities) == 1
    assert entities[0]["entity_type"] == "EMAIL"
    assert entities[0]["audio_start_ms"] <= 1120
    assert entities[0]["audio_end_ms"] >= 1380
    assert entities[0]["text"] == "john@example.com"


@pytest.mark.asyncio
async def test_entity_spanning_window_boundary_detected_with_context_carryover():
    detector = SlidingWindowDetector(
        FakeDetectionEngine(),
        TimelineMapper(),
        window_ms=500,
        overlap_ms=250,
    )

    await detector.process_chunk("Reach john@", audio_start_ms=0, audio_duration_ms=250)
    entities = await detector.process_chunk("example.com today", audio_start_ms=250, audio_duration_ms=250)  # noqa: E501

    assert [entity["entity_type"] for entity in entities] == ["EMAIL"]
    assert entities[0]["audio_start_ms"] < 250
    assert entities[0]["audio_end_ms"] > 250


@pytest.mark.asyncio
async def test_multiple_entities_in_same_window_produce_multiple_timeline_entries():
    detector = SlidingWindowDetector(
        FakeDetectionEngine(),
        TimelineMapper(),
        window_ms=500,
        overlap_ms=125,
    )

    entities = await detector.process_chunk(
        "Jane Doe uses john@example.com",
        audio_start_ms=0,
        audio_duration_ms=500,
    )

    assert [entity["entity_type"] for entity in entities] == ["EMAIL", "PERSON"]
    assert all(entity["audio_start_ms"] < entity["audio_end_ms"] for entity in entities)
