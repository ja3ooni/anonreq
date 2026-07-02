from __future__ import annotations

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.models import DetectionResult
from anonreq.models.processing_context import ProcessingContext


class SlidingWindowDetector:
    def __init__(self, engine: FirewallRuleEngine, window_size: int = 2048) -> None:
        self._engine = engine
        self._window_size = window_size
        self._buffer = ""

    async def ingest(self, chunk: str) -> list[DetectionResult]:
        self._buffer += chunk
        if len(self._buffer) > self._window_size:
            excess = len(self._buffer) - self._window_size
            self._buffer = self._buffer[excess:]
        return await self._engine.evaluate(self._buffer)

    async def flush(self) -> list[DetectionResult]:
        results = await self._engine.evaluate(self._buffer)
        self._buffer = ""
        return results

    def reset(self) -> None:
        self._buffer = ""


class StreamingFirewallDetector:
    def __init__(self, engine: FirewallRuleEngine, window_size: int = 2048) -> None:
        self._detector = SlidingWindowDetector(engine, window_size=window_size)

    async def process_chunk(
        self,
        chunk: bytes,
        ctx: ProcessingContext,
    ) -> tuple[bytes, list[DetectionResult]]:
        text = chunk.decode("utf-8", errors="replace")
        results = await self._detector.ingest(text)
        return chunk, results
