from __future__ import annotations

import pytest

from anonreq.voice.transcript_buffer import TranscriptBuffer


@pytest.mark.asyncio
async def test_transcript_buffer_stores_last_n_chunks_with_overlap_window():
    buffer = TranscriptBuffer(max_chunks=3, window_ms=500, overlap_ms=125)
    await buffer.add_chunk("first", 0)
    await buffer.add_chunk("second", 250)
    await buffer.add_chunk("third", 500)
    await buffer.add_chunk("fourth", 750)

    assert len(buffer) == 3
    assert [segment.text for segment in buffer.as_list()] == ["second", "third", "fourth"]
    assert [item["text"] for item in buffer.get_window(750)] == ["second", "third", "fourth"]


@pytest.mark.asyncio
async def test_transcript_buffer_assembles_contiguous_text_in_timestamp_order():
    buffer = TranscriptBuffer(max_chunks=10, window_ms=500, overlap_ms=125)
    await buffer.add_chunk("world again", 200)
    await buffer.add_chunk("hello world", 100)
    await buffer.add_chunk("again soon", 300)

    assert buffer.assemble_contiguous() == "hello world again soon"


@pytest.mark.asyncio
async def test_transcript_buffer_clear_before_prunes_old_entries():
    buffer = TranscriptBuffer(max_chunks=10, window_ms=500, overlap_ms=125)
    await buffer.add_chunk("old", 100)
    await buffer.add_chunk("new", 600)
    buffer.clear_before(500)

    assert [segment.text for segment in buffer.as_list()] == ["new"]


@pytest.mark.asyncio
async def test_transcript_buffer_ignores_empty_chunks():
    buffer = TranscriptBuffer()
    await buffer.add_chunk("   ", 100)
    assert len(buffer) == 0


def test_transcript_buffer_rejects_invalid_window_parameters():
    with pytest.raises(ValueError):
        TranscriptBuffer(max_chunks=0)
    with pytest.raises(ValueError):
        TranscriptBuffer(window_ms=500, overlap_ms=500)

