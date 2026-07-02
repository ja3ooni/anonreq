"""Integration tests for ScanStage and StreamScanStage.

Tests verify:
- Non-streaming ScanStage scans after restoration and increments counter
- ScanStage does NOT increment counter when no tokens present
- ScanStage never modifies or blocks the response (AG-17)
- StreamScanStage scans full assembled text after FINISH event
- StreamScanStage never blocks emission (AG-17)
- Both stages log warning when unrestored tokens found
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from anonreq.monitoring.metrics import unrestored_tokens
from anonreq.verification.scanner import ResponseScanner
from anonreq.verification.stages import ScanStage, StreamScanStage


@pytest.fixture(autouse=True)
def reset_unrestored_counter():
    """Reset the unrestored_tokens counter before each test."""
    unrestored_tokens.clear()


@pytest.fixture
def processing_context():
    """Create a minimal ProcessingContext for scan stage testing."""
    from anonreq.models.processing_context import ProcessingContext

    return ProcessingContext(request_id="test_scan_001")


class TestNonStreamingScanStage:
    """ScanStage for non-streaming responses."""

    async def test_detects_unrestored_tokens_and_increments_counter(self, processing_context):
        processing_context.restored_response = {"content": "Hello [NAME_1], your email [EMAIL_0] was found"}
        stage = ScanStage()
        await stage.execute(processing_context)
        # Counter should have been incremented for 2 tokens
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        # Note: we count by iterating the actual counter metric
        assert total == 2

    async def test_no_counter_when_tokens_absent(self, processing_context):
        processing_context.restored_response = {"content": "All tokens restored successfully"}
        stage = ScanStage()
        await stage.execute(processing_context)
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        assert total == 0

    async def test_no_counter_when_restored_response_none(self, processing_context):
        processing_context.restored_response = None
        stage = ScanStage()
        await stage.execute(processing_context)
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        assert total == 0

    async def test_never_modifies_response(self, processing_context):
        original = {"content": "Hello [NAME_1]"}
        processing_context.restored_response = dict(original)
        stage = ScanStage()
        await stage.execute(processing_context)
        assert processing_context.restored_response == original

    async def test_never_blocks_or_raises(self, processing_context):
        processing_context.restored_response = {"content": "Leaked [TOKEN_1]"}
        stage = ScanStage()
        # Must not raise
        await stage.execute(processing_context)
        # Context should have no errors added
        assert not processing_context.has_errors()

    async def test_logs_warning_when_tokens_found(self, processing_context, caplog):
        caplog.set_level(logging.WARNING)
        processing_context.restored_response = {"content": "[NAME_1] leaked"}
        stage = ScanStage()
        await stage.execute(processing_context)
        assert any(
            "Unrestored tokens detected after restoration" in record.message
            for record in caplog.records
        )


class TestStreamScanStage:
    """StreamScanStage for streaming responses."""

    async def test_detects_tokens_in_assembled_text(self, processing_context):
        processing_context.assembled_response = "Stream complete. Contact [EMAIL_0] for help."
        stage = StreamScanStage()
        await stage.execute(processing_context)
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        assert total == 1

    async def test_no_counter_when_assembled_text_clean(self, processing_context):
        processing_context.assembled_response = "Stream complete. All good."
        stage = StreamScanStage()
        await stage.execute(processing_context)
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        assert total == 0

    async def test_no_counter_when_assembled_response_none(self, processing_context):
        processing_context.assembled_response = None
        stage = StreamScanStage()
        await stage.execute(processing_context)
        total = unrestored_tokens.labels(entity_type="UNKNOWN")._value.get()
        assert total == 0

    async def test_never_blocks_or_raises(self, processing_context):
        processing_context.assembled_response = "Leaked [TOKEN_1]"
        stage = StreamScanStage()
        await stage.execute(processing_context)
        assert not processing_context.has_errors()

    async def test_logs_warning_when_tokens_found(self, processing_context, caplog):
        caplog.set_level(logging.WARNING)
        processing_context.assembled_response = "[PHONE_1] leaked in stream"
        stage = StreamScanStage()
        await stage.execute(processing_context)
        assert any(
            "Unrestored tokens detected in streamed response" in record.message
            for record in caplog.records
        )
