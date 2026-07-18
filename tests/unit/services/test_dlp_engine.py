"""Unit tests for DLPEngine."""

from __future__ import annotations

import pytest

from anonreq.models.dlp import DLPAction, DLPCategory
from anonreq.services.dlp_engine import DLPEngine


@pytest.fixture
def dlp_engine() -> DLPEngine:
    config = {
        "core_categories": {
            "PII": {
                "default_action": "block",
                "patterns": [
                    {"id": "ssn", "regex": r"\d{3}-\d{2}-\d{4}", "action": "block"},
                    {
                        "id": "email",
                        "regex": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                        "action": "anonymize",
                    },
                ],
            },
            "CREDENTIALS": {
                "default_action": "block",
                "patterns": [
                    {"id": "password_field", "regex": r"password\s*[:=]\s*\S+", "action": "block"},
                ],
            },
        },
        "exfiltration": {},
    }
    return DLPEngine(config)


@pytest.mark.unit
class TestDLPEngine:
    @pytest.mark.anyio
    async def test_detects_ssn(self, dlp_engine: DLPEngine) -> None:
        result = await dlp_engine.inspect("My SSN is 123-45-6789", "tenant-1")
        assert len(result.detections) >= 1
        assert any(d.category == DLPCategory.PII for d in result.detections)

    @pytest.mark.anyio
    async def test_no_detections_on_clean_text(self, dlp_engine: DLPEngine) -> None:
        result = await dlp_engine.inspect("Hello world, nice weather today", "tenant-1")
        assert len(result.detections) == 0

    @pytest.mark.anyio
    async def test_max_action_computed(self, dlp_engine: DLPEngine) -> None:
        result = await dlp_engine.inspect(
            "SSN: 111-22-3333 and email: test@example.com", "tenant-1"
        )
        assert result.max_action in (DLPAction.BLOCK, DLPAction.ANONYMIZE, DLPAction.REDACT)

    @pytest.mark.anyio
    async def test_tenant_scoped_patterns(self, dlp_engine: DLPEngine) -> None:
        dlp_engine.load_tenant_patterns("tenant-1", {
            "patterns": [{"id": "custom_id", "regex": r"CUST-\d{6}", "action": "quarantine"}]
        })
        result = await dlp_engine.inspect("Order CUST-123456", "tenant-1")
        assert len(result.detections) >= 1

    @pytest.mark.anyio
    async def test_quarantine_result_structure(self, dlp_engine: DLPEngine) -> None:
        from anonreq.models.processing_context import ProcessingContext

        ctx = ProcessingContext(
            request_id="req-1",
            tenant_id="tenant-1",
            text_nodes=[{"value": "SSN: 999-88-7777"}],
        )
        dlp_result = await dlp_engine.inspect_request(ctx)
        qr = await dlp_engine.quarantine_request(ctx, dlp_result)
        assert qr.action == "quarantine"
        assert qr.tenant_id == "tenant-1"
        assert qr.detection_count >= 1
