"""Unit tests for DLP quarantine action (Plan 13-03, Task 1).

Tests cover:
- QuarantineResult dataclass structure
- DLPEngine.quarantine_request() metadata-only behavior
- Audit event emission (no payload)
- Response structure boundaries
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.models.dlp import DLPAction, DLPCategory, DLPDetection, DLPResult
from anonreq.services.dlp_engine import DLPEngine, QuarantineResult
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def dlp_config():
    import yaml
    with open("config/dlp.yaml", "r") as f:
        data = yaml.safe_load(f)
    return data["dlp"]


@pytest.fixture
def dlp_engine(dlp_config):
    return DLPEngine(dlp_config)


def test_quarantine_result_dataclass():
    """QuarantineResult has all required metadata fields (no payload)."""
    result = QuarantineResult(
        event_id="q_abc123def456",
        tenant_id="test_tenant",
        request_id="req_001",
        category="PII",
        action="quarantine",
        detection_count=1,
        max_action="block",
        timestamp="2026-07-04T12:00:00",
    )
    assert result.event_id == "q_abc123def456"
    assert result.tenant_id == "test_tenant"
    assert result.request_id == "req_001"
    assert result.category == "PII"
    assert result.action == "quarantine"
    assert result.detection_count == 1
    assert result.max_action == "block"
    assert result.timestamp == "2026-07-04T12:00:00"
    # Verify no payload fields exist
    assert not hasattr(result, "match_text")
    assert not hasattr(result, "original_content")
    assert not hasattr(result, "provider_response")


@pytest.mark.asyncio
async def test_quarantine_request_returns_metadata_only(dlp_engine):
    """quarantine_request() returns QuarantineResult with metadata only."""
    ctx = ProcessingContext(request_id="req_quarantine_001", tenant_id="tenant_a")
    ctx.audit_chain = AsyncMock()

    dlp_result = DLPResult(
        tenant_id="tenant_a",
        detections=[
            DLPDetection(
                category=DLPCategory.PII,
                action=DLPAction.BLOCK,
                match_text="john@example.com",
                confidence=0.9,
                start=0,
                end=15,
                pattern_id="pii_email",
            ),
        ],
        max_action=DLPAction.BLOCK,
        is_blocked=True,
        is_quarantined=False,
    )

    result = await dlp_engine.quarantine_request(ctx, dlp_result)

    # Must return a QuarantineResult
    assert isinstance(result, QuarantineResult)
    assert result.event_id.startswith("q_")
    assert result.tenant_id == "tenant_a"
    assert result.request_id == "req_quarantine_001"
    assert result.category == DLPCategory.PII.value
    assert result.action == "quarantine"
    assert result.detection_count == 1
    assert result.max_action == DLPAction.BLOCK.value
    assert result.timestamp is not None


@pytest.mark.asyncio
async def test_quarantine_request_no_detections(dlp_engine):
    """quarantine_request() handles empty detections gracefully."""
    ctx = ProcessingContext(request_id="req_quarantine_002", tenant_id="tenant_b")
    ctx.audit_chain = AsyncMock()

    dlp_result = DLPResult(
        tenant_id="tenant_b",
        detections=[],
        max_action=DLPAction.ALLOW,
        is_blocked=False,
        is_quarantined=False,
    )

    result = await dlp_engine.quarantine_request(ctx, dlp_result)
    assert result.category == "unknown"
    assert result.detection_count == 0
    assert result.max_action == DLPAction.ALLOW.value


@pytest.mark.asyncio
async def test_quarantine_emits_audit_event(dlp_engine):
    """quarantine_request() emits dlp_violation audit event with metadata only."""
    ctx = ProcessingContext(request_id="req_quarantine_003", tenant_id="tenant_c")
    ctx.audit_chain = AsyncMock()

    dlp_result = DLPResult(
        tenant_id="tenant_c",
        detections=[
            DLPDetection(
                category=DLPCategory.INTELLECTUAL_PROPERTY,
                action=DLPAction.QUARANTINE,
                match_text="trade secret formula",
                confidence=0.9,
                start=0,
                end=18,
                pattern_id="ip_trade_secret",
            ),
        ],
        max_action=DLPAction.QUARANTINE,
        is_blocked=True,
        is_quarantined=True,
    )

    await dlp_engine.quarantine_request(ctx, dlp_result)

    # Audit event should have been emitted
    ctx.audit_chain.log_event.assert_awaited_once_with(
        "dlp_violation",
        event_id=ctx.audit_chain.log_event.call_args[1]["event_id"],
        tenant_id="tenant_c",
        request_id="req_quarantine_003",
        category=DLPCategory.INTELLECTUAL_PROPERTY.value,
        action="quarantine",
        detection_count=1,
        max_action=DLPAction.QUARANTINE.value,
        timestamp=ctx.audit_chain.log_event.call_args[1]["timestamp"],
    )

    # Verify NO payload fields in audit event
    audit_kwargs = ctx.audit_chain.log_event.call_args[1]
    assert "match_text" not in audit_kwargs
    assert "original_content" not in audit_kwargs
    assert "provider_response" not in audit_kwargs


@pytest.mark.asyncio
async def test_quarantine_audit_no_payload_content(dlp_engine):
    """Quarantine audit event NEVER contains match_text or raw content."""
    ctx = ProcessingContext(request_id="req_quarantine_004", tenant_id="tenant_d")
    ctx.audit_chain = AsyncMock()

    dlp_result = DLPResult(
        tenant_id="tenant_d",
        detections=[
            DLPDetection(
                category=DLPCategory.CREDENTIALS,
                action=DLPAction.BLOCK,
                match_text="password: 'supersecret123'",
                confidence=0.9,
                start=0,
                end=24,
                pattern_id="cred_password",
            ),
            DLPDetection(
                category=DLPCategory.PII,
                action=DLPAction.BLOCK,
                match_text="john.doe@example.com",
                confidence=0.9,
                start=25,
                end=44,
                pattern_id="pii_email",
            ),
        ],
        max_action=DLPAction.BLOCK,
        is_blocked=True,
        is_quarantined=False,
    )

    await dlp_engine.quarantine_request(ctx, dlp_result)

    # Verify audit event fields
    audit_kwargs = ctx.audit_chain.log_event.call_args[1]
    # Metadata fields present
    assert "event_id" in audit_kwargs
    assert "tenant_id" in audit_kwargs
    assert "request_id" in audit_kwargs
    assert "category" in audit_kwargs
    assert "action" in audit_kwargs
    assert "detection_count" in audit_kwargs
    assert audit_kwargs["detection_count"] == 2
    # Payload fields ABSENT
    assert "match_text" not in audit_kwargs
    assert "raw_request" not in audit_kwargs
    assert "original_content" not in audit_kwargs


@pytest.mark.asyncio
async def test_quarantine_response_structure_boundary(dlp_engine):
    """QuarantineResult response body has metadata-only structure."""
    ctx = ProcessingContext(request_id="req_quarantine_005", tenant_id="tenant_e")
    ctx.audit_chain = AsyncMock()

    dlp_result = DLPResult(
        tenant_id="tenant_e",
        detections=[
            DLPDetection(
                category=DLPCategory.HEALTH,
                action=DLPAction.BLOCK,
                match_text="PHI data",
                confidence=0.9,
                start=0,
                end=8,
                pattern_id="health_hipaa",
            ),
        ],
        max_action=DLPAction.BLOCK,
        is_blocked=True,
        is_quarantined=False,
    )

    result = await dlp_engine.quarantine_request(ctx, dlp_result)

    # Build the response body structure that the route handler would use
    response_body = {
        "error": "request_quarantined",
        "detail": "Request quarantined by DLP policy",
        "quarantine": {
            "event_id": result.event_id,
            "category": result.category,
            "action": result.action,
            "timestamp": result.timestamp,
        },
    }

    # Metadata fields present
    assert response_body["error"] == "request_quarantined"
    assert "event_id" in response_body["quarantine"]
    assert "category" in response_body["quarantine"]
    assert "action" in response_body["quarantine"]
    assert "timestamp" in response_body["quarantine"]

    # Payload fields ABSENT from entire response
    assert "original_content" not in response_body
    assert "match_text" not in response_body
    assert "matched_text" not in response_body
    assert "provider_response" not in response_body


@pytest.mark.asyncio
async def test_dlp_engine_detects_base64_exfiltration(dlp_engine):
    """DLPEngine.inspect() detects Base64 as EXFILTRATION category."""
    text = "SGVsbG9Xb3JsZFNvbWV0aGluZ01vcmU="
    result = await dlp_engine.inspect(text)
    exf_results = [d for d in result.detections if d.category == DLPCategory.EXFILTRATION]
    assert len(exf_results) >= 1
    assert exf_results[0].action == DLPAction.BLOCK
    assert exf_results[0].pattern_id.startswith("exfiltration_")
    assert exf_results[0].match_text == "[EXFILTRATION_DETECTED]"


@pytest.mark.asyncio
async def test_dlp_engine_detects_hex_exfiltration(dlp_engine):
    """DLPEngine.inspect() detects hex-encoded text as EXFILTRATION."""
    text = "The hex block: 48656c6c6f20576f726c64205468697320697320612074657374 more text"
    result = await dlp_engine.inspect(text)
    exf_results = [d for d in result.detections if d.category == DLPCategory.EXFILTRATION]
    assert len(exf_results) >= 1


@pytest.mark.asyncio
async def test_dlp_engine_combined_exfiltration_and_category(dlp_engine):
    """DLPEngine.inspect() returns both exfiltration and category DLP detections."""
    text = "My email is john@example.com and here is the encoded: SGVsbG9Xb3JsZFNvbWV0aGluZ01vcmU="
    result = await dlp_engine.inspect(text)
    # Should detect both PII (email) and EXFILTRATION (base64)
    categories = {d.category for d in result.detections}
    assert DLPCategory.PII in categories
    assert DLPCategory.EXFILTRATION in categories
    # Exfiltration uses BLOCK action
    exf_results = [d for d in result.detections if d.category == DLPCategory.EXFILTRATION]
    assert exf_results[0].action == DLPAction.BLOCK
    # Combined result should be blocked
    assert result.is_blocked is True
    assert result.max_action in (DLPAction.BLOCK,)


@pytest.mark.asyncio
async def test_dlp_engine_exfiltration_metadata_only(dlp_engine):
    """Exfiltration detection in DLPEngine uses metadata-only placeholders."""
    text = "SGVsbG9Xb3JsZFNvbWV0aGluZ01vcmU="
    result = await dlp_engine.inspect(text)
    exf_results = [d for d in result.detections if d.category == DLPCategory.EXFILTRATION]
    if exf_results:
        # match_text is placeholder, NOT the actual encoded content
        assert exf_results[0].match_text == "[EXFILTRATION_DETECTED]"


@pytest.mark.asyncio
async def test_dlp_engine_no_exfiltration_on_normal_text(dlp_engine):
    """Normal English text does NOT produce exfiltration detections."""
    text = "The quick brown fox jumps over the lazy dog"
    result = await dlp_engine.inspect(text)
    exf_results = [d for d in result.detections if d.category == DLPCategory.EXFILTRATION]
    assert len(exf_results) == 0
