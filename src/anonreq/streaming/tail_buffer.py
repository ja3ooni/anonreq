"""TailBuffer FSM — reassembles streaming chunks with partial-token safety.

Per D-59 through D-65 and DOMAIN-MODEL.md:

FSM states: COLLECTING → MATCHING → FLUSHING → COLLECTING (loop) → TERMINATED

- COLLECTING: append incoming chunk, transition to MATCHING.
- MATCHING: if full token match → FLUSHING; if partial match at buffer tail
  → COLLECTING (wait for more data); if no match → FLUSHING.
- FLUSHING: emit safe content before tail window, retain tail window.
- TERMINATED: reject further ingestion.

Key guarantee (AG-05): the TailBuffer never emits partial token matches. A
partial ``[TYPE_N`` at a chunk boundary is retained in the buffer until the
completing chunk arrives, and only then flushed.
"""

from __future__ import annotations

import re
import time
import asyncio
from collections.abc import AsyncIterator
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anonreq.streaming.stream_event import StreamEvent

TOKEN_PATTERN = re.compile(r"\[[A-Z][A-Z_]{0,19}_\d+\]")
"""Regex matching a complete ``[TYPE_N]`` token at the buffer frontier."""

PARTIAL_PATTERN = re.compile(r"\[[A-Za-z][A-Za-z_]{0,19}_?\d*$")
"""Regex matching a partial ``[TYPE_N`` at the end of the buffer (no closing bracket)."""


class BufferState(str, Enum):
    """TailBuffer FSM states per D-59."""

    COLLECTING = "COLLECTING"
    MATCHING = "MATCHING"
    FLUSHING = "FLUSHING"
    TERMINATED = "TERMINATED"


class TailBuffer:
    """Finite state machine for safe streaming token reassembly.

    Ingests ``StreamEvent`` instances, buffers TEXT_DELTA content, and
    yields assembled text chunks that are guaranteed to contain complete
    ``[TYPE_N]`` tokens only — no partial matches cross chunk boundaries.

    Non-TEXT_DELTA events (TOOL_CALL_DELTA, REASONING_DELTA, FINISH,
    ERROR, etc.) bypass the FSM entirely and are yielded as-is (D-56).
    """

    # ── Configuration constants ──────────────────────────────────────────────
    TAIL_WINDOW_CHARS: int = 128
    """Number of trailing characters retained as the tail window (D-62)."""

    MAX_BUFFER_CHARS: int = 2048
    """Maximum accumulated characters before forced flush (D-63)."""

    MAX_BUFFER_AGE_MS: int = 1000
    """Maximum time in milliseconds before age-based flush (D-63)."""

    # ── Instance fields ──────────────────────────────────────────────────────

    def __init__(self) -> None:
        self.active_buffer: str = ""
        """Accumulated text content from TEXT_DELTA events."""

        self.tail_window: str = ""
        """Tail window retained across flush cycles (D-62)."""

        self.state: BufferState = BufferState.COLLECTING
        """Current FSM state per D-59."""

        self.last_flush_at: float = time.monotonic()
        """Timestamp of last flush (for age-based flush)."""

        self._lock = asyncio.Lock()

    # ── Public API ───────────────────────────────────────────────────────────

    async def ingest(self, event: StreamEvent) -> AsyncIterator[str]:
        """Process a ``StreamEvent`` through the FSM.

        Args:
            event: A ``StreamEvent`` from the provider stream. Only
                ``TEXT_DELTA`` events enter the FSM — all other event
                types (TOOL_CALL_DELTA, REASONING_DELTA, FINISH, ERROR,
                HEARTBEAT, START) bypass the FSM and are yielded as-is.

        Yields:
            Assembled text chunks (from TEXT_DELTA) or event payload
            strings (for non-TEXT_DELTA events).
        """
        chunks: list[str] = []
        async with self._lock:
            if self.state == BufferState.TERMINATED:
                return

            event_type = event.event_type.value if hasattr(event.event_type, "value") else event.event_type

            if event_type != "TEXT_DELTA":
                text = self._format_non_text_delta(event)
                if text:
                    chunks.append(text)
            else:
                if event.delta_text:
                    self.active_buffer += event.delta_text
                self.state = BufferState.MATCHING
                chunks.extend([chunk async for chunk in self._match()])

        for chunk in chunks:
            yield chunk

    def terminate(self) -> None:
        """Set the FSM to TERMINATED state.

        After calling this, ``ingest()`` will no-op and further calls to
        ``flush_remaining()`` will still return the buffer contents.
        """
        self.state = BufferState.TERMINATED

    def flush_remaining(self) -> str:
        """Flush the entire buffer including the tail window.

        Returns:
            The complete buffer content. After this call, the buffer is
            cleared and the state remains TERMINATED.
        """
        remaining = self.active_buffer
        self.active_buffer = ""
        self.tail_window = ""
        return remaining

    # ── Internal FSM transitions ─────────────────────────────────────────────

    async def _match(self) -> AsyncIterator[str]:
        """MATCHING state: scan buffer for token patterns.

        Transitions:
        - Full ``[TYPE_N]`` match near frontier → FLUSHING
        - Partial token at tail (incomplete ``[TYPE_N) → COLLECTING
        - No match → FLUSHING

        Yields:
            Emitted text chunks from FLUSHING state.
        """
        # Check age-based flush trigger
        if self.last_flush_at > 0:
            age_ms = (time.monotonic() - self.last_flush_at) * 1000
            if age_ms >= self.MAX_BUFFER_AGE_MS:
                async for chunk in self._flush():
                    yield chunk
                return

        # Check size-based flush trigger
        if len(self.active_buffer) >= self.MAX_BUFFER_CHARS:
            async for chunk in self._flush():
                yield chunk
            return

        # Scan for token patterns near the buffer tail
        tail_region = self.active_buffer[-self.TAIL_WINDOW_CHARS:] if len(self.active_buffer) > self.TAIL_WINDOW_CHARS else self.active_buffer

        # Check for complete token at or near boundary
        if TOKEN_PATTERN.search(tail_region):
            # Full token match → FLUSHING
            async for chunk in self._flush():
                yield chunk
            return

        # Check for partial token at the very end of the buffer
        if PARTIAL_PATTERN.search(tail_region):
            # Partial match at tail → wait for more data
            self.state = BufferState.COLLECTING
            return

        # No match → FLUSHING
        async for chunk in self._flush():
            yield chunk

    async def _flush(self) -> AsyncIterator[str]:
        """FLUSHING state: emit safe content before tail window.

        The tail window (last ``TAIL_WINDOW_CHARS`` chars) is retained
        for the next round to handle tokens that may cross chunk boundaries.

        Yields:
            The safe prefix (content before the tail window).
        """
        self.state = BufferState.FLUSHING

        buffer_len = len(self.active_buffer)

        if buffer_len <= self.TAIL_WINDOW_CHARS:
            # Buffer fits entirely within tail window. Keep it buffered so
            # finish/disconnect handling can flush it without data loss.
            self.tail_window = self.active_buffer
        else:
            # Emit safe prefix, retain tail window
            safe_end = buffer_len - self.TAIL_WINDOW_CHARS
            safe_prefix = self.active_buffer[:safe_end]
            self.tail_window = self.active_buffer[safe_end:]
            self.active_buffer = self.tail_window

            if safe_prefix:
                yield safe_prefix

        self.last_flush_at = time.monotonic()
        self.state = BufferState.COLLECTING

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _format_non_text_delta(self, event: StreamEvent) -> str:
        """Format a non-TEXT_DELTA event as a string for emission.

        Args:
            event: The StreamEvent to format.

        Returns:
            A string representation, or empty string if no content.
        """
        event_type = event.event_type.value if hasattr(event.event_type, "value") else event.event_type

        if event_type == "REASONING_DELTA" and event.reasoning:
            return event.reasoning
        elif event_type == "TOOL_CALL_DELTA":
            return event.tool_call.model_dump_json() if event.tool_call else "{}"
        elif event_type == "FINISH":
            finish_val = event.finish_reason.value if hasattr(event.finish_reason, "value") else str(event.finish_reason) if event.finish_reason else "STOP"
            return finish_val
        elif event_type == "ERROR":
            return event.metadata.get("error", "Unknown error") if event.metadata else "Unknown error"
        elif event_type == "START":
            return ""
        elif event_type == "HEARTBEAT":
            return ""
        return ""
