from __future__ import annotations

import pytest

from anonreq.firewall.audit import FirewallAuditEvent, FirewallAuditPublisher
from anonreq.firewall.metrics import FirewallMetrics
from anonreq.firewall.models import (
    DetectionCategory,
    DetectionResult,
    FirewallAction,
    SeverityLevel,
)
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def ctx() -> ProcessingContext:
    return ProcessingContext(request_id="test_audit", tenant_id="test_tenant")


@pytest.fixture
def detection_result() -> DetectionResult:
    return DetectionResult(
        category=DetectionCategory.PROMPT_INJECTION,
        confidence=0.95,
        rule_id="test_rule_01",
        severity=SeverityLevel.HIGH,
        action=FirewallAction.BLOCK,
        matched_text_snippet="ignore all previous",
    )


class TestFirewallAuditEvent:
    def test_event_enum_values(self):
        assert FirewallAuditEvent.INJECTION_DETECTED.value == "firewall_injection_detected"
        assert FirewallAuditEvent.OUTBOUND_VIOLATION.value == "firewall_outbound_violation"
        assert FirewallAuditEvent.RULE_RELOADED.value == "firewall_rule_reloaded"


class TestFirewallAuditPublisher:
    @pytest.mark.asyncio
    async def test_publish_injection_contains_required_fields(self, ctx, detection_result):
        publisher = FirewallAuditPublisher()
        await publisher.publish_injection(detection_result, ctx)
        event = ctx.audit_metadata["firewall_event"]
        assert event["event_type"] == "firewall_injection_detected"
        assert event["category"] == "prompt_injection"
        assert event["confidence"] == 0.95
        assert event["severity"] == "HIGH"
        assert event["action"] == "BLOCK"
        assert event["rule_id"] == "test_rule_01"

    @pytest.mark.asyncio
    async def test_publish_outbound_violation(self, ctx, detection_result):
        publisher = FirewallAuditPublisher()
        await publisher.publish_outbound_violation(detection_result, ctx)
        event = ctx.audit_metadata["firewall_event"]
        assert event["event_type"] == "firewall_outbound_violation"
        assert event["severity"] == "HIGH"
        assert event["action"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_publish_rule_reloaded(self):
        publisher = FirewallAuditPublisher()
        event_data = await publisher.publish_rule_reloaded(old_count=10, new_count=15, version="2.0")  # noqa: E501
        assert event_data["event_type"] == "firewall_rule_reloaded"
        assert event_data["old_rule_count"] == 10
        assert event_data["new_rule_count"] == 15
        assert event_data["version"] == "2.0"
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_no_raw_content_in_injection_event(self, ctx, detection_result):
        publisher = FirewallAuditPublisher()
        await publisher.publish_injection(detection_result, ctx)
        event = ctx.audit_metadata["firewall_event"]
        event_str = str(event)
        assert "john@example.com" not in event_str
        assert "test@test.com" not in event_str

    @pytest.mark.asyncio
    async def test_snippet_truncated_to_50_chars(self):
        publisher = FirewallAuditPublisher()
        long_snippet = "X" * 200
        truncated = publisher._truncate_snippet(long_snippet, max_chars=50)
        assert len(truncated) == 53
        assert truncated.endswith("...")
        assert truncated.startswith("X" * 50)

    @pytest.mark.asyncio
    async def test_snippet_short_not_truncated(self):
        publisher = FirewallAuditPublisher()
        snippet = "short text"
        result = publisher._truncate_snippet(snippet, max_chars=50)
        assert result == "short text"

    @pytest.mark.asyncio
    async def test_snippet_none_returns_none(self):
        publisher = FirewallAuditPublisher()
        assert publisher._truncate_snippet(None) is None


class TestFirewallMetrics:
    def test_metrics_registered(self):
        FirewallMetrics.reset()
        metrics = FirewallMetrics.get_instance()
        assert metrics is not None

    def test_record_injection_increments_counter(self):
        FirewallMetrics.reset()
        metrics = FirewallMetrics.get_instance()
        metrics.record_injection(tenant_id="test_tenant", category="prompt_injection")
        sample = metrics.prompt_security_events.labels(
            event_type="injection_detected",
            tenant_id="test_tenant",
            category="prompt_injection",
        )
        assert sample._value.get() == 1.0

    def test_record_outbound_violation_increments_counter(self):
        FirewallMetrics.reset()
        metrics = FirewallMetrics.get_instance()
        metrics.record_outbound_violation(tenant_id="test_tenant", category="system_prompt_extraction")  # noqa: E501
        sample = metrics.prompt_security_events.labels(
            event_type="outbound_violation",
            tenant_id="test_tenant",
            category="system_prompt_extraction",
        )
        assert sample._value.get() == 1.0

    def test_record_rule_reload_increments_counter(self):
        FirewallMetrics.reset()
        metrics = FirewallMetrics.get_instance()
        metrics.record_rule_reload()
        sample = metrics.prompt_security_events.labels(
            event_type="rule_reloaded",
            tenant_id="",
            category="",
        )
        assert sample._value.get() == 1.0

    def test_multiple_increments_accumulate(self):
        FirewallMetrics.reset()
        metrics = FirewallMetrics.get_instance()
        for _ in range(5):
            metrics.record_injection(tenant_id="t1", category="jailbreak")
        sample = metrics.prompt_security_events.labels(
            event_type="injection_detected",
            tenant_id="t1",
            category="jailbreak",
        )
        assert sample._value.get() == 5.0
