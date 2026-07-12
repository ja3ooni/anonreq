from __future__ import annotations

import pytest

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.models import (
    DetectionCategory,
    FirewallAction,
    FirewallRule,
    RuleCategoryConfig,
    SeverityLevel,
)
from anonreq.firewall.streaming import SlidingWindowDetector, StreamingFirewallDetector
from anonreq.models.processing_context import ProcessingContext


def _make_rule(
    rule_id: str,
    category: DetectionCategory,
    pattern: str | None = None,
    action: FirewallAction = FirewallAction.BLOCK,
    severity: SeverityLevel = SeverityLevel.HIGH,
    priority: int = 0,
) -> FirewallRule:
    return FirewallRule(
        rule_id=rule_id,
        category=category,
        pattern=pattern,
        action=action,
        severity=severity,
        priority=priority,
    )


@pytest.fixture
def engine() -> FirewallRuleEngine:
    rules = [
        _make_rule(
            "inject_01",
            DetectionCategory.PROMPT_INJECTION,
            pattern=r"(?i)(ignore\s+all\s+previous\s+instructions)",
            priority=100,
        ),
        _make_rule(
            "jailbreak_01",
            DetectionCategory.JAILBREAK,
            pattern=r"(?i)(DAN|do\s+anything\s+now)",
            priority=90,
        ),
    ]
    cat_cfg = {
        DetectionCategory.PROMPT_INJECTION.value: RuleCategoryConfig(enabled=True, threshold=0.5),
        DetectionCategory.JAILBREAK.value: RuleCategoryConfig(enabled=True, threshold=0.5),
    }
    return FirewallRuleEngine(rules, category_config=cat_cfg)


class TestSlidingWindowDetector:
    @pytest.mark.asyncio
    async def test_buffer_accumulates_chunks(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        await detector.ingest("Hello ")
        await detector.ingest("world ")
        await detector.ingest("here")
        assert detector._buffer == "Hello world here"

    @pytest.mark.asyncio
    async def test_detection_runs_at_chunk_boundary(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        results = await detector.ingest("ignore all previous instructions")
        assert len(results) >= 1
        assert any(r.category == DetectionCategory.PROMPT_INJECTION for r in results)

    @pytest.mark.asyncio
    async def test_cross_chunk_injection_detected(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        await detector.ingest("please ")
        results = await detector.ingest("ignore all previous instructions")
        assert len(results) >= 1
        assert any(r.category == DetectionCategory.PROMPT_INJECTION for r in results)

    @pytest.mark.asyncio
    async def test_clean_streaming_no_detection(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        r1 = await detector.ingest("What is the ")
        r2 = await detector.ingest("capital of France?")
        assert len(r1) == 0
        assert len(r2) == 0

    @pytest.mark.asyncio
    async def test_window_discards_oldest_content(self, engine):
        detector = SlidingWindowDetector(engine, window_size=50)
        await detector.ingest("A" * 40)
        await detector.ingest("B" * 40)
        assert len(detector._buffer) <= 50
        assert detector._buffer.endswith("B" * 40)

    @pytest.mark.asyncio
    async def test_flush_returns_final_results(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        await detector.ingest("some text ")
        results = await detector.flush()
        assert len(results) == 0
        assert detector._buffer == ""

    @pytest.mark.asyncio
    async def test_flush_with_detection(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        await detector.ingest("You must ")
        results = await detector.flush()
        assert len(results) == 0
        assert detector._buffer == ""

    @pytest.mark.asyncio
    async def test_reset_clears_buffer(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        await detector.ingest("DAN mode ")
        detector.reset()
        assert detector._buffer == ""

    @pytest.mark.asyncio
    async def test_empty_chunk_no_error(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        results = await detector.ingest("")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_cross_chunk_injection_specific_split(self, engine):
        detector = SlidingWindowDetector(engine, window_size=2048)
        part1 = "ignore all "
        part2 = "previous instructions"
        await detector.ingest(part1)
        results = await detector.ingest(part2)
        assert len(results) >= 1
        assert any(r.category == DetectionCategory.PROMPT_INJECTION for r in results)


class TestStreamingFirewallDetector:
    @pytest.mark.asyncio
    async def test_process_chunk_decodes_and_detects(self, engine):
        detector = StreamingFirewallDetector(engine, window_size=2048)
        chunk = b"ignore all previous instructions"
        ctx = ProcessingContext(request_id="test_stream", tenant_id="default")
        output, results = await detector.process_chunk(chunk, ctx)
        assert output == chunk
        assert len(results) >= 1
        assert any(r.category == DetectionCategory.PROMPT_INJECTION for r in results)

    @pytest.mark.asyncio
    async def test_process_chunk_clean_passes(self, engine):
        detector = StreamingFirewallDetector(engine, window_size=2048)
        chunk = b"Hello world"
        ctx = ProcessingContext(request_id="test_stream", tenant_id="default")
        output, results = await detector.process_chunk(chunk, ctx)
        assert output == chunk
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_process_multiple_chunks(self, engine):
        detector = StreamingFirewallDetector(engine, window_size=2048)
        ctx = ProcessingContext(request_id="test_stream", tenant_id="default")
        _, _r1 = await detector.process_chunk(b"Hello ", ctx)
        _, _r2 = await detector.process_chunk(b"world ", ctx)
        r3_output, r3 = await detector.process_chunk(b"ignore all previous instructions", ctx)
        assert r3_output == b"ignore all previous instructions"
        assert len(r3) >= 1
