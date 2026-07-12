from __future__ import annotations

import time
from typing import Any

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.ml_model import MLModel
from anonreq.firewall.models import (
    DetectionResult,
    FirewallAction,
    SeverityActionMapping,
    SeverityLevel,
)
from anonreq.models.processing_context import ProcessingContext


class InboundFirewallGate:
    def __init__(
        self,
        engine: FirewallRuleEngine,
        ml_model: MLModel | None = None,
    ) -> None:
        self._engine = engine
        self._ml_model = ml_model

    async def check_pre_anon(self, text: str, ctx: ProcessingContext) -> list[DetectionResult]:
        start = time.monotonic()
        results = await self._engine.evaluate(text)
        if self._ml_model and results:
            results = await self._engine.evaluate_with_ml(text, self._ml_model)
        elapsed = (time.monotonic() - start) * 1000
        ctx.audit_metadata["inbound_firewall_latency_ms"] = round(elapsed, 2)
        return results

    async def check_post_anon(self, sanitized_text: str, ctx: ProcessingContext) -> list[DetectionResult]:  # noqa: E501
        start = time.monotonic()
        results = await self._engine.evaluate(sanitized_text)
        elapsed = (time.monotonic() - start) * 1000
        ctx.audit_metadata["post_anon_firewall_latency_ms"] = round(elapsed, 2)
        return results

    def _should_block(self, results: list[DetectionResult]) -> bool:
        return any(r.action == FirewallAction.BLOCK for r in results)

    def _get_block_response(self, result: DetectionResult) -> tuple[int, dict[str, Any]]:
        return (
            400,
            {
                "error": {
                    "message": f"Request blocked by security firewall: {result.category.value}",
                    "type": "firewall_blocked",
                    "code": result.category.value,
                    "request_id": None,
                }
            },
        )

    def _emit_audit(self, result: DetectionResult, ctx: ProcessingContext) -> None:
        ctx.audit_metadata["firewall_event"] = {
            "event_type": "firewall_injection_detected",
            "category": result.category.value,
            "confidence": result.confidence,
            "severity": result.severity.value,
            "action": result.action.value,
            "rule_id": result.rule_id,
        }


class OutboundFirewallGate:
    def __init__(
        self,
        engine: FirewallRuleEngine,
        severity_mapping: SeverityActionMapping,
        ml_model: MLModel | None = None,
    ) -> None:
        self._engine = engine
        self._severity_mapping = severity_mapping
        self._ml_model = ml_model

    async def check_pre_restore(self, provider_output: str, ctx: ProcessingContext) -> list[DetectionResult]:  # noqa: E501
        start = time.monotonic()
        results = await self._engine.evaluate(provider_output)
        if self._ml_model and results:
            results = await self._engine.evaluate_with_ml(provider_output, self._ml_model)
        elapsed = (time.monotonic() - start) * 1000
        ctx.audit_metadata["pre_restore_firewall_latency_ms"] = round(elapsed, 2)
        return self._apply_severity_mapping(results)

    async def check_post_restore(self, restored_output: str, ctx: ProcessingContext) -> list[DetectionResult]:  # noqa: E501
        start = time.monotonic()
        results = await self._engine.evaluate(restored_output)
        elapsed = (time.monotonic() - start) * 1000
        ctx.audit_metadata["post_restore_firewall_latency_ms"] = round(elapsed, 2)
        return self._apply_severity_mapping(results)

    def _apply_severity_mapping(self, results: list[DetectionResult]) -> list[DetectionResult]:
        mapped: list[DetectionResult] = []
        for r in results:
            mapped_action = self._get_outbound_action(r)
            mapped.append(
                DetectionResult(
                    category=r.category,
                    confidence=r.confidence,
                    rule_id=r.rule_id,
                    severity=r.severity,
                    action=mapped_action,
                    matched_text_snippet=r.matched_text_snippet,
                )
            )
        return mapped

    def _get_outbound_action(self, result: DetectionResult) -> FirewallAction:
        mapping: dict[SeverityLevel, FirewallAction] = {
            SeverityLevel.HIGH: self._severity_mapping.high,
            SeverityLevel.MEDIUM: self._severity_mapping.medium,
            SeverityLevel.LOW: self._severity_mapping.low,
        }
        return mapping.get(result.severity, FirewallAction.MONITOR)

    def _get_block_response(self, result: DetectionResult) -> tuple[int, dict[str, Any]]:
        return (
            451,
            {
                "error": {
                    "message": f"Output blocked by security firewall: {result.category.value}",
                    "type": "firewall_blocked",
                    "code": "output_policy_violation",
                    "request_id": None,
                }
            },
        )

    def _emit_audit(self, result: DetectionResult, ctx: ProcessingContext) -> None:
        ctx.audit_metadata["firewall_event"] = {
            "event_type": "firewall_outbound_violation",
            "category": result.category.value,
            "confidence": result.confidence,
            "severity": result.severity.value,
            "action": result.action.value,
            "rule_id": result.rule_id,
        }
