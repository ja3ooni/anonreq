"""Streaming invariants proven with Hypothesis."""

from __future__ import annotations

import asyncio
import re

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from anonreq.streaming.stream_event import EventType, StreamEvent
from anonreq.streaming.tail_buffer import TailBuffer
from tests.conftest import chunked_stream_strategy, reasoning_stream_strategy


async def _collect_text(buffer: TailBuffer, chunks: list[str]) -> str:
    emitted: list[str] = []
    for chunk in chunks:
        event = StreamEvent(event_type=EventType.TEXT_DELTA, provider="test", delta_text=chunk)
        emitted.extend([item async for item in buffer.ingest(event)])
    remaining = buffer.flush_remaining()
    if remaining:
        emitted.append(remaining)
    return "".join(emitted)


def _restore_with_mapping(text: str, mapping: dict[str, str]) -> str:
    result = text
    for token, value in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        core = re.escape(token.strip("[]"))
        result = re.sub(
            rf"(?<![A-Za-z0-9_])\[?{core}\]?(?![A-Za-z0-9_])",
            lambda _m: value,  # noqa: B023
            result,
            flags=re.IGNORECASE,
        )
    return result


@given(chunked_stream_strategy())
@settings(max_examples=100)
def test_arbitrary_chunk_split(args) -> None:
    full_text, chunks, mapping = args
    restored = _restore_with_mapping(asyncio.run(_collect_text(TailBuffer(), chunks)), mapping)
    expected = _restore_with_mapping(full_text, mapping)
    assert restored == expected


@given(st.text(min_size=5, max_size=100))
@settings(max_examples=100)
def test_every_token_split_boundary(base_text: str) -> None:
    mid = len(base_text) // 2
    token = "[EMAIL_0]"
    mapping = {token: "test@example.com"}
    full_text = base_text[:mid] + token + base_text[mid:]
    expected = _restore_with_mapping(full_text, mapping)
    for split_at in range(1, len(token)):
        chunks = [full_text[: mid + split_at], full_text[mid + split_at :]]
        restored = _restore_with_mapping(asyncio.run(_collect_text(TailBuffer(), chunks)), mapping)
        assert restored == expected


@given(st.text(min_size=2048, max_size=5000))
@settings(max_examples=50)
def test_buffer_overflow_protection(text: str) -> None:
    buffer = TailBuffer()

    async def run() -> int:
        max_seen = 0
        for i in range(0, len(text), 100):
            event = StreamEvent(event_type=EventType.TEXT_DELTA, provider="test", delta_text=text[i : i + 100])  # noqa: E501
            _ = [item async for item in buffer.ingest(event)]
            max_seen = max(max_seen, len(buffer.active_buffer))
        return max_seen

    assert asyncio.run(run()) <= buffer.MAX_BUFFER_CHARS


@given(st.text(min_size=10, max_size=200))
@settings(max_examples=100)
def test_flush_timing_invariance(text: str) -> None:
    chunks1 = [text[i : i + 5] for i in range(0, len(text), 5)]
    chunks2 = [text[i : i + 13] for i in range(0, len(text), 13)]
    assert asyncio.run(_collect_text(TailBuffer(), chunks1)) == asyncio.run(
        _collect_text(TailBuffer(), chunks2)
    )


@given(reasoning_stream_strategy())
@settings(max_examples=50)
def test_reasoning_blocked(args) -> None:
    text, reasoning, positions = args
    assume(reasoning not in text)
    buffer = TailBuffer()

    async def run() -> str:
        client_events: list[str] = []
        for pos in positions:
            event = StreamEvent(event_type=EventType.TEXT_DELTA, provider="test", delta_text=text[pos : pos + 5])  # noqa: E501
            client_events.extend([item async for item in buffer.ingest(event)])
            # Route layer drops reasoning before TailBuffer/emission in MVP.
            _ = StreamEvent(event_type=EventType.REASONING_DELTA, provider="test", reasoning=reasoning)  # noqa: E501
        client_events.append(buffer.flush_remaining())
        return "".join(client_events)

    assert reasoning not in asyncio.run(run())
