from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from anonreq.firewall.models import DetectionResult
from anonreq.models.processing_context import ProcessingContext


class FirewallAuditEvent(StrEnum):
    INJECTION_DETECTED = "firewall_injection_detected"
    OUTBOUND_VIOLATION = "firewall_outbound_violation"
    RULE_RELOADED = "firewall_rule_reloaded"


class FirewallAuditPublisher:
    async def publish_injection(self, result: DetectionResult, ctx: ProcessingContext) -> None:
        ctx.audit_metadata["firewall_event"] = {
            "event_type": FirewallAuditEvent.INJECTION_DETECTED.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "tenant_id": ctx.tenant_id,
            "session_id": ctx.context_id,
            "category": result.category.value,
            "confidence": result.confidence,
            "rule_id": result.rule_id,
            "severity": result.severity.value,
            "action": result.action.value,
            "matched_text_snippet": self._truncate_snippet(result.matched_text_snippet),
        }

    async def publish_outbound_violation(self, result: DetectionResult, ctx: ProcessingContext) -> None:  # noqa: E501
        ctx.audit_metadata["firewall_event"] = {
            "event_type": FirewallAuditEvent.OUTBOUND_VIOLATION.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "tenant_id": ctx.tenant_id,
            "session_id": ctx.context_id,
            "category": result.category.value,
            "confidence": result.confidence,
            "rule_id": result.rule_id,
            "severity": result.severity.value,
            "action": result.action.value,
            "matched_text_snippet": self._truncate_snippet(result.matched_text_snippet),
        }

    async def publish_rule_reloaded(
        self,
        old_count: int,
        new_count: int,
        version: str,
    ) -> dict[str, Any]:
        event = {
            "event_type": FirewallAuditEvent.RULE_RELOADED.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "old_rule_count": old_count,
            "new_rule_count": new_count,
            "version": version,
        }
        return event

    def _truncate_snippet(self, text: str | None, max_chars: int = 50) -> str | None:
        if text is None:
            return None
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."
