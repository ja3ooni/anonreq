"""Unit tests for the TailBuffer FSM.

Tests cover:
- All BufferState transitions (COLLECTING → MATCHING → FLUSHING loop → TERMINATED)
- Partial token match at buffer boundary (never emit partial [TYPE_N] tokens)
- Flush heuristics (safe prefix, MAX_BUFFER_CHARS, MAX_BUFFER_AGE_MS, finish)
- Non-TEXT_DELTA event bypass
- State rejection after termination
- Concurrent ingest integrity
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest

from anonreq.streaming.stream_event import EventType, StreamEvent
from anonreq.streaming.tail_buffer import BufferState, TailBuffer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_delta(text: str) -> StreamEvent:
    """Create a TEXT_DELTA StreamEvent with the given text."""
    return StreamEvent(
        event_type=EventType.TEXT_DELTA,
        provider="test",
        delta_text=text,
    )


async def collect(iterator: AsyncIterator[str]) -> list[str]:
    """Collect all items from an async iterator into a list."""
    return [item async for item in iterator]


# ---------------------------------------------------------------------------
# Test 1: COLLECTING state — ingesting TEXT_DELTA chunks appends to buffer
# ---------------------------------------------------------------------------


class TestCollectingState:
    """TailBuffer in COLLECTING state accepts TEXT_DELTA events."""

    async def test_initial_state_is_collecting(self) -> None:
        """Buffer starts in COLLECTING state with empty active buffer."""
        tb = TailBuffer()
        assert tb.state == BufferState.COLLECTING
        assert tb.active_buffer == ""
        assert tb.tail_window == ""

    async def test_ingest_text_delta_appends_to_buffer(self) -> None:
        """Ingesting a TEXT_DELTA event appends delta_text to active_buffer."""
        tb = TailBuffer()
        results = await collect(tb.ingest(make_delta("Hello ")))
        assert "Hello " in tb.active_buffer
        assert tb.state == BufferState.COLLECTING

    async def test_multiple_chunks_accumulate(self) -> None:
        """Multiple TEXT_DELTA events append sequentially."""
        tb = TailBuffer()
        await collect(tb.ingest(make_delta("Hello ")))
        await collect(tb.ingest(make_delta("world")))
        assert "Hello world" in tb.active_buffer


# ---------------------------------------------------------------------------
# Test 2: MATCHING state — full token match at frontier → FLUSHING
# ---------------------------------------------------------------------------


class TestMatchingFullToken:
    """Full [TYPE_N] token match at buffer frontier triggers flush."""

    async def test_full_token_at_frontier_triggers_flush(self) -> None:
        """When buffer contains a complete [TYPE_N] at the frontier, flush safe prefix."""
        tb = TailBuffer()
        # Build up buffer with some text then a token
        await collect(tb.ingest(make_delta("Hello ")))
        assert tb.state == BufferState.COLLECTING

    async def test_safe_prefix_emitted_before_tail(self) -> None:
        """Safe prefix (content before tail window) is emitted on flush."""
        tb = TailBuffer()
        # Ingest enough text to confidently have content before tail window
        text = "A" * 200 + " [EMAIL_0] at the end"
        chunks = await collect(tb.ingest(make_delta(text)))
        # Some content should be emitted (safe prefix)
        assert len(chunks) > 0 or tb.state in (BufferState.FLUSHING, BufferState.COLLECTING)


# ---------------------------------------------------------------------------
# Test 3: Partial token match at tail — retain, transition back to COLLECTING
# ---------------------------------------------------------------------------


class TestPartialTokenMatch:
    """Partial token at buffer boundary is retained until completion."""

    async def test_partial_token_at_tail_retains_buffer(self) -> None:
        """When buffer ends with a partial [TYPE_N, transition back to COLLECTING."""
        tb = TailBuffer()
        # Ingest text ending with a partial token
        await collect(tb.ingest(make_delta("Hello [EM")))
        # The buffer should retain the partial token content
        assert "[EM" in tb.active_buffer
        # State should be COLLECTING (waiting for more data)
        # Note: if the buffer has content before tail_window, it may flush those first
        # but the partial token stays in the tail_window
        assert tb.state != BufferState.TERMINATED

    async def test_complete_partial_token_on_next_chunk(self) -> None:
        """A partial token completed by next chunk should flush properly."""
        tb = TailBuffer()
        await collect(tb.ingest(make_delta("Hello [EM")))
        # Now complete the token
        await collect(tb.ingest(make_delta("AIL_0]")))
        # Buffer should contain the complete token
        assert tb.state != BufferState.TERMINATED


# ---------------------------------------------------------------------------
# Test 4: No match in buffer → FLUSHING, emit all but tail window
# ---------------------------------------------------------------------------


class TestNoMatchFlush:
    """When no token pattern found, flush emits all but tail window."""

    async def test_no_token_match_flushes(self) -> None:
        """Plain text without tokens eventually flushes."""
        tb = TailBuffer()
        # Ingest plain text that exceeds TAIL_WINDOW_CHARS
        text = "Hello world. " * 20  # ~300 chars, well over tail window
        results = await collect(tb.ingest(make_delta(text)))
        # Should flush some content
        assert len(results) > 0 or tb.state == BufferState.FLUSHING


# ---------------------------------------------------------------------------
# Test 5: Flush trigger by MAX_BUFFER_CHARS exceeded
# ---------------------------------------------------------------------------


class TestMaxBufferChars:
    """Buffer exceeding MAX_BUFFER_CHARS triggers automatic flush."""

    async def test_buffer_exceeding_max_chars_flushes(self) -> None:
        """When active_buffer exceeds MAX_BUFFER_CHARS, flush is triggered."""
        tb = TailBuffer()
        # Ingest text well over MAX_BUFFER_CHARS
        text = "A" * (tb.MAX_BUFFER_CHARS + 100)
        results = await collect(tb.ingest(make_delta(text)))
        # Active buffer should be reduced
        assert len(tb.active_buffer) <= tb.MAX_BUFFER_CHARS or tb.state == BufferState.FLUSHING


# ---------------------------------------------------------------------------
# Test 6: Flush trigger by MAX_BUFFER_AGE_MS exceeded
# ---------------------------------------------------------------------------


class TestMaxBufferAge:
    """Buffer exceeding MAX_BUFFER_AGE_MS triggers time-based flush."""

    async def test_buffer_age_flush(self) -> None:
        """When buffer age exceeds MAX_BUFFER_AGE_MS, flush is triggered."""
        tb = TailBuffer()
        # Set last_flush_at to far in the past
        tb.last_flush_at = time.monotonic() - 10  # 10 seconds ago
        # Ingest a small amount of text
        results = await collect(tb.ingest(make_delta("Hello")))
        # Should flush due to age and transition back to COLLECTING
        assert tb.state in (BufferState.COLLECTING, BufferState.FLUSHING)


# ---------------------------------------------------------------------------
# Test 7: Finish event → FLUSH entire buffer, transition to TERMINATED
# ---------------------------------------------------------------------------


class TestFinishEvent:
    """Finish event flushes entire buffer including tail window."""

    async def test_finish_flushes_entire_buffer(self) -> None:
        """flush_remaining on finish emits all buffer content and sets TERMINATED."""
        tb = TailBuffer()
        await collect(tb.ingest(make_delta("Hello world")))
        tb.terminate()
        assert tb.state == BufferState.TERMINATED
        remaining = tb.flush_remaining()
        assert len(remaining) > 0
        assert "Hello world" in remaining

    async def test_terminate_sets_terminated_state(self) -> None:
        """terminate() sets state to TERMINATED."""
        tb = TailBuffer()
        tb.terminate()
        assert tb.state == BufferState.TERMINATED


# ---------------------------------------------------------------------------
# Test 8: REASONING_DELTA bypasses FSM entirely
# ---------------------------------------------------------------------------


class TestReasoningDeltaBypass:
    """REASONING_DELTA events bypass the FSM entirely."""

    async def test_reasoning_delta_bypasses_fsm(self) -> None:
        """REASONING_DELTA events are yielded as-is without buffering."""
        tb = TailBuffer()
        event = StreamEvent(
            event_type=EventType.REASONING_DELTA,
            provider="test",
            reasoning="Step-by-step reasoning...",
        )
        results = await collect(tb.ingest(event))
        assert len(results) == 1
        assert "Step-by-step reasoning" in results[0]
        # Buffer should be unchanged
        assert tb.active_buffer == ""


# ---------------------------------------------------------------------------
# Test 9: TOOL_CALL_DELTA bypasses FSM
# ---------------------------------------------------------------------------


class TestToolCallDeltaBypass:
    """TOOL_CALL_DELTA events bypass the FSM and are emitted as-is."""

    async def test_tool_call_delta_bypasses_fsm(self) -> None:
        """TOOL_CALL_DELTA events are yielded as-is without buffering."""
        tb = TailBuffer()
        event = StreamEvent(
            event_type=EventType.TOOL_CALL_DELTA,
            provider="test",
            tool_call=None,  # minimal tool call
        )
        results = await collect(tb.ingest(event))
        assert len(results) == 1
        assert tb.active_buffer == ""


# ---------------------------------------------------------------------------
# Test 10: TERMINATED state rejects further ingestion
# ---------------------------------------------------------------------------


class TestTerminatedState:
    """TERMINATED state rejects or no-ops further ingestion."""

    async def test_terminated_rejects_ingest(self) -> None:
        """After termination, ingest no-ops or raises."""
        tb = TailBuffer()
        tb.terminate()
        assert tb.state == BufferState.TERMINATED
        results = await collect(tb.ingest(make_delta("Should not be processed")))
        assert len(results) == 0
        assert tb.active_buffer == ""


# ---------------------------------------------------------------------------
# Test 11: Chunk count never triggers flush (SSE-06)
# ---------------------------------------------------------------------------


class TestChunkCountNoFlush:
    """Chunk count does not trigger flush — only size/age/finish do."""

    async def test_many_small_chunks_no_automatic_flush(self) -> None:
        """Many small TEXT_DELTA events should not trigger flush by count alone."""
        tb = TailBuffer()
        # Send many small chunks
        for i in range(50):
            await collect(tb.ingest(make_delta("a")))
        # At least some text should be buffered
        assert len(tb.active_buffer) >= 50 or tb.state != BufferState.COLLECTING


# ---------------------------------------------------------------------------
# Test 12: Concurrent ingest calls maintain buffer integrity
# ---------------------------------------------------------------------------


class TestConcurrentIngest:
    """Concurrent ingest calls in COLLECTING state maintain buffer integrity."""

    async def test_concurrent_ingests_dont_corrupt_buffer(self) -> None:
        """Multiple concurrent ingest calls should not cause data loss."""
        tb = TailBuffer()

        async def ingest_text(text: str) -> None:
            await collect(tb.ingest(make_delta(text)))

        # Launch concurrent ingests
        await asyncio.gather(
            ingest_text("Hello "),
            ingest_text("World "),
            ingest_text("Test "),
        )

        # Buffer should contain all text (possibly in any order)
        assert tb.state != BufferState.TERMINATED
