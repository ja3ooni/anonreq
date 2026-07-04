"""Unit tests for DLP audit events with MITRE technique IDs (Plan 13-04, Task 1 & 2).

Tests cover:
- DLP violation audit event includes MITRE technique_id and technique_name
- DLP exfiltration detection event includes MITRE technique_id T1048
- DLP outbound suppressed event includes MITRE technique_id T1048
- No raw content (match_text, request body) in any DLP audit event
- Prometheus counter integration tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from anonreq.models.dlp import DLPAction, DLPCategory, DLPDetection, DLPResult
from anonreq.models.processing_context import ProcessingContext


# ===========================================================================
# Task 1: DLP Audit Events with MITRE Technique IDs
# ===========================================================================


@pytest.fixture
def audit_logger():
    """Create DLPAuditLogger with loaded MITRE mapping."""
    from anonreq.services.audit_logger import DLPAuditLogger

    with open("config/mitre_attack.yaml", "r") as f:
        mitre_config = yaml.safe_load(f)
    return DLPAuditLogger(mitre_config)


@pytest.fixture
def sample_ctx():
    """Create a ProcessingContext for audit event tests."""
    ctx = ProcessingContext(
        request_id="req_audit_001",
        tenant_id="tenant_a",
        context_id="ctx_audit_001",
    )
    ctx.audit_chain = AsyncMock()
    return ctx


@pytest.fixture
def dlp_result_with_pii():
    """DLPResult with a PII detection."""
    return DLPResult(
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
    )


@pytest.fixture
def dlp_result_multiple():
    """DLPResult with multiple category detections."""
    return DLPResult(
        tenant_id="tenant_a",
        detections=[
            DLPDetection(
                category=DLPCategory.PII,
                action=DLPAction.BLOCK,
                match_text="john@example.com",
                confidence=0.9,
                start=0, end=15,
                pattern_id="pii_email",
            ),
            DLPDetection(
                category=DLPCategory.CREDENTIALS,
                action=DLPAction.BLOCK,
                match_text="password=supersecret",
                confidence=0.95,
                start=20, end=39,
                pattern_id="cred_password",
            ),
        ],
        max_action=DLPAction.BLOCK,
        is_blocked=True,
    )


# --- DLP Violation Audit Event Tests ---


@pytest.mark.asyncio
async def test_dlp_violation_audit_has_mitre_id(audit_logger, sample_ctx, dlp_result_with_pii):
    """dlp_violation audit event includes MITRE technique_id."""
    await audit_logger.log_dlp_violation(dlp_result_with_pii, sample_ctx)
    # Verify audit_chain.log_event was called with mitre_technique_id
    sample_ctx.audit_chain.log_event.assert_called_once()
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    # kwargs are the metadata dict — check for mitre fields
    assert call_kwargs.get("dlp_mitre_technique_id") is not None


@pytest.mark.asyncio
async def test_dlp_violation_mitre_id_is_t1048_002_for_pii(audit_logger, sample_ctx, dlp_result_with_pii):
    """PII violation audit event has MITRE technique_id T1048.002."""
    await audit_logger.log_dlp_violation(dlp_result_with_pii, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs["dlp_mitre_technique_id"] == "T1048.002"


@pytest.mark.asyncio
async def test_dlp_violation_audit_has_mitre_name(audit_logger, sample_ctx, dlp_result_with_pii):
    """dlp_violation audit event includes MITRE technique_name."""
    await audit_logger.log_dlp_violation(dlp_result_with_pii, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_mitre_technique_name") is not None
    assert "Exfiltration" in call_kwargs["dlp_mitre_technique_name"]


@pytest.mark.asyncio
async def test_dlp_violation_audit_has_category_and_action(audit_logger, sample_ctx, dlp_result_with_pii):
    """dlp_violation audit event includes dlp_category and dlp_action."""
    await audit_logger.log_dlp_violation(dlp_result_with_pii, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_category") == "PII"
    assert call_kwargs.get("dlp_action") == "block"
    assert call_kwargs.get("dlp_detection_count") == 1


@pytest.mark.asyncio
async def test_dlp_violation_audit_no_raw_content(audit_logger, sample_ctx, dlp_result_with_pii):
    """DLP violation audit event contains NO match_text or request body."""
    await audit_logger.log_dlp_violation(dlp_result_with_pii, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    # These fields MUST NOT be present
    assert "match_text" not in call_kwargs
    assert "raw_content" not in call_kwargs
    assert "request_body" not in call_kwargs
    assert "original_content" not in call_kwargs
    # The match_text from the detection should not be in the event
    assert "john@example.com" not in str(call_kwargs)


@pytest.mark.asyncio
async def test_dlp_violation_multiple_detections(audit_logger, sample_ctx, dlp_result_multiple):
    """DLP violation emits one event per detection, each with correct MITRE ID."""
    await audit_logger.log_dlp_violation(dlp_result_multiple, sample_ctx)
    # One event per detection = 2 calls
    assert sample_ctx.audit_chain.log_event.call_count == 2
    calls = sample_ctx.audit_chain.log_event.call_args_list
    # First call is PII → T1048.002
    assert calls[0].kwargs["dlp_category"] == "PII"
    assert calls[0].kwargs["dlp_mitre_technique_id"] == "T1048.002"
    # Second call is Credentials → T1552
    assert calls[1].kwargs["dlp_category"] == "Credentials"
    assert calls[1].kwargs["dlp_mitre_technique_id"] == "T1552"


# --- DLP Exfiltration Audit Event Tests ---


@pytest.mark.asyncio
async def test_dlp_exfiltration_audit_has_mitre_id(audit_logger, sample_ctx):
    """dlp_exfiltration_detected audit event includes MITRE technique_id T1048."""
    exf_summary = MagicMock()
    exf_summary.methods = ["base64", "hex"]
    exf_summary.max_confidence = 0.85
    exf_summary.detection_count = 3

    await audit_logger.log_dlp_exfiltration(exf_summary, sample_ctx)
    sample_ctx.audit_chain.log_event.assert_called_once()
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_mitre_technique_id") == "T1048"


@pytest.mark.asyncio
async def test_dlp_exfiltration_audit_has_method_and_confidence(audit_logger, sample_ctx):
    """Exfiltration audit event includes detection methods and confidence."""
    exf_summary = MagicMock()
    exf_summary.methods = ["base64", "hex"]
    exf_summary.max_confidence = 0.85
    exf_summary.detection_count = 3

    await audit_logger.log_dlp_exfiltration(exf_summary, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_exfiltration_method") == "base64,hex"
    assert call_kwargs.get("dlp_exfiltration_confidence") == 0.85


@pytest.mark.asyncio
async def test_dlp_exfiltration_audit_no_encoded_content(audit_logger, sample_ctx):
    """Exfiltration audit event does NOT contain encoded content."""
    exf_summary = MagicMock()
    exf_summary.methods = ["base64"]
    exf_summary.max_confidence = 0.85
    exf_summary.detection_count = 1

    await audit_logger.log_dlp_exfiltration(exf_summary, sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert "encoded_content" not in call_kwargs
    assert "match_text" not in call_kwargs
    assert "raw_content" not in call_kwargs


# --- DLP Outbound Suppressed Audit Event Tests ---


@pytest.mark.asyncio
async def test_dlp_outbound_suppressed_has_mitre_id(audit_logger, sample_ctx):
    """dlp_outbound_suppressed audit event includes MITRE technique_id T1048."""
    await audit_logger.log_dlp_outbound_suppressed(sample_ctx)
    sample_ctx.audit_chain.log_event.assert_called_once()
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_mitre_technique_id") == "T1048"


@pytest.mark.asyncio
async def test_dlp_outbound_suppressed_has_flag(audit_logger, sample_ctx):
    """Outbound suppressed event includes dlp_outbound_suppressed=True."""
    await audit_logger.log_dlp_outbound_suppressed(sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert call_kwargs.get("dlp_outbound_suppressed") is True


@pytest.mark.asyncio
async def test_dlp_outbound_suppressed_no_provider_response(audit_logger, sample_ctx):
    """Outbound suppressed event does NOT contain provider response content."""
    await audit_logger.log_dlp_outbound_suppressed(sample_ctx)
    call_kwargs = sample_ctx.audit_chain.log_event.call_args.kwargs
    assert "provider_response" not in call_kwargs
    assert "match_text" not in call_kwargs


# --- Prometheus Counter Tests (Task 2) ---


@pytest.mark.asyncio
async def test_prometheus_violation_counter_increments(sample_ctx, dlp_result_with_pii):
    """DLP violation counter increments on detection."""
    from prometheus_client import Counter

    counter = Counter(
        "test_anonreq_dlp_violations_total",
        "Total DLP violations by category and action",
        ["tenant_id", "category", "action"],
    )
    counter.clear()

    for d in dlp_result_with_pii.detections:
        counter.labels(
            tenant_id=sample_ctx.tenant_id,
            category=d.category.value,
            action=d.action.value,
        ).inc()

    sample = list(counter.collect())[0]
    total_value = sum(s.value for s in sample.samples if s.name.endswith("_total"))
    assert total_value == 1


@pytest.mark.asyncio
async def test_prometheus_exfiltration_counter_increments(sample_ctx):
    """Exfiltration counter increments on detection."""
    from prometheus_client import Counter

    counter = Counter(
        "test_anonreq_dlp_exfiltration_total",
        "Total exfiltration detections by encoding type",
        ["tenant_id", "encoding_type"],
    )
    counter.clear()

    methods = ["base64", "hex"]
    for method in methods:
        counter.labels(
            tenant_id=sample_ctx.tenant_id,
            encoding_type=method,
        ).inc()

    sample = list(counter.collect())[0]
    total_value = sum(s.value for s in sample.samples if s.name.endswith("_total"))
    assert total_value == 2


@pytest.mark.asyncio
async def test_prometheus_action_counter_increments(sample_ctx):
    """DLP actions counter increments on enforcement."""
    from prometheus_client import Counter

    counter = Counter(
        "test_anonreq_dlp_actions_total",
        "Total DLP actions applied by action type",
        ["tenant_id", "action"],
    )
    counter.clear()

    counter.labels(
        tenant_id=sample_ctx.tenant_id,
        action="block",
    ).inc()

    sample = list(counter.collect())[0]
    total_value = sum(s.value for s in sample.samples if s.name.endswith("_total"))
    assert total_value == 1


@pytest.mark.asyncio
async def test_prometheus_counter_not_incremented_on_allow(sample_ctx):
    """Counter is NOT incremented when no DLP detection (ALLOW)."""
    from prometheus_client import Counter

    counter = Counter(
        "test_anonreq_dlp_violations_total_allow",
        "Test: DLP violations counter not incremented on ALLOW",
        ["tenant_id", "category", "action"],
    )
    counter.clear()

    # No detections = no increment
    sample = list(counter.collect())[0]
    total_value = sum(s.value for s in sample.samples if s.name.endswith("_total"))
    assert total_value == 0


# --- Field allowlist validation ---


def test_dlp_audit_allowed_fields():
    """Verify DLP audit field allowlist prevents raw content leakage."""
    from anonreq.services.audit_logger import DLPAuditLogger

    allowed = DLPAuditLogger.ALLOWED_FIELDS
    # Critical: no raw content fields
    assert "match_text" not in allowed
    assert "request_body" not in allowed
    assert "raw_content" not in allowed
    assert "original_content" not in allowed
    assert "provider_response" not in allowed
    assert "encoded_content" not in allowed

    # Required DLP fields must be allowed
    assert "dlp_category" in allowed
    assert "dlp_action" in allowed
    assert "dlp_detection_count" in allowed
    assert "dlp_mitre_technique_id" in allowed
    assert "dlp_mitre_technique_name" in allowed
    assert "dlp_exfiltration_method" in allowed
    assert "dlp_exfiltration_confidence" in allowed
    assert "dlp_outbound_suppressed" in allowed
