from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from starlette.responses import JSONResponse, Response

from anonreq.firewall.classifier import ONNXClassifier, StructuralClassifier
from anonreq.firewall.config import FIREWALL_DECISIONS, FirewallConfig
from anonreq.firewall.injection_scorer import InjectionScorer
from anonreq.firewall.jailbreak_db import JailbreakDB
from anonreq.firewall.metrics import (
    firewall_blocks_total,
    firewall_evaluation_duration_ms,
    firewall_latency_budget_exceeded_total,
)
from anonreq.firewall.override_detector import OverrideDetector

EVENT_BY_DETECTION_TYPE = {
    "prompt_injection": "prompt_injection_blocked",
    "semantic_injection": "prompt_injection_blocked",
    "jailbreak": "jailbreak_blocked",
    "role_manipulation": "role_manipulation",
    "system_prompt_override": "model_theft_attempt",
    "model_theft_attempt": "model_theft_attempt",
    "data_poisoning": "data_poisoning_attempt",
    "supply_chain": "supply_chain_compromise",
}


@dataclass(frozen=True)
class FirewallDecision:
    action: FIREWALL_DECISIONS
    confidence: float
    detection_type: str | None = None
    mitre_atlas_id: str | None = None
    latency_ms: float = 0.0
    event_type: str | None = None
    audit_event: dict[str, Any] | None = None

    @property
    def allowed(self) -> bool:
        return self.action == FIREWALL_DECISIONS.ALLOW


@dataclass
class FirewallMetricsRecorder:
    tenant_id: str = "default"
    latency_budget_ms: int = 20

    def record(self, decision: FirewallDecision) -> None:
        firewall_evaluation_duration_ms.labels(decision=decision.action.value.lower()).observe(decision.latency_ms)
        if decision.latency_ms > self.latency_budget_ms:
            firewall_latency_budget_exceeded_total.inc()
        if decision.action == FIREWALL_DECISIONS.BLOCK:
            firewall_blocks_total.labels(
                detection_type=decision.detection_type or "unknown",
                tenant_id=self.tenant_id,
            ).inc()


class FirewallPipeline:
    """Inline AI firewall gate that runs before downstream request processing."""

    def __init__(
        self,
        config: FirewallConfig | None = None,
        jailbreak_db: JailbreakDB | None = None,
        injection_scorer: InjectionScorer | None = None,
        override_detector: OverrideDetector | None = None,
        mitre_map: dict[str, Any] | None = None,
        classifier: ONNXClassifier | None = None,
        structural_classifier: StructuralClassifier | None = None,
        metrics: FirewallMetricsRecorder | None = None,
        audit_sink: Any | None = None,
    ) -> None:
        self.config = config or FirewallConfig()
        self.jailbreak_db = jailbreak_db or JailbreakDB(self.config.jailbreak_db_path)
        self.injection_scorer = injection_scorer or InjectionScorer(
            embedding_model=self.config.embedding_model,
            threshold=self.config.injection_threshold,
        )
        self.override_detector = override_detector or OverrideDetector(self.config)
        self.classifier = classifier
        self.structural_classifier = structural_classifier or StructuralClassifier()
        self.mitre_map = mitre_map or load_mitre_atlas_map(self.config.mitre_atlas_path)
        self.metrics = metrics or FirewallMetricsRecorder(latency_budget_ms=self.config.latency_budget_ms)  # noqa: E501
        self.audit_sink = audit_sink

    async def evaluate(self, request_text: str) -> FirewallDecision:
        start = time.perf_counter()
        try:
            if not self.config.enabled:
                return self._allow(start)

            structural = self.structural_classifier.classify(request_text)
            if structural.detected and structural.score >= self.config.jailbreak_threshold:
                return await self._block(
                    start,
                    detection_type=structural.detection_type or "prompt_injection",
                    confidence=structural.score,
                    rule_id=structural.rule_id,
                )

            jailbreak_matches = self.jailbreak_db.match(request_text)
            if jailbreak_matches:
                best = jailbreak_matches[0]
                if best["confidence"] >= self.config.jailbreak_threshold:
                    return await self._block(
                        start,
                        detection_type="jailbreak",
                        confidence=best["confidence"],
                        rule_id=best["pattern_id"],
                    )

            override_score = self.override_detector.score(request_text)
            if self.override_detector.classify(request_text, override_score):
                return await self._block(
                    start,
                    detection_type="system_prompt_override",
                    confidence=override_score,
                    rule_id="OVERRIDE-001",
                )

            if self._needs_semantic_scan(structural.score, jailbreak_matches, override_score):
                semantic_score = await self.injection_scorer.score(request_text)
                if self.injection_scorer.classify(semantic_score):
                    return await self._block(
                        start,
                        detection_type="semantic_injection",
                        confidence=semantic_score,
                        rule_id="SEMANTIC-001",
                    )

            if self.classifier is not None:
                classifier_score = self.classifier.score(request_text)
                if classifier_score >= self.config.injection_threshold:
                    return await self._block(
                        start,
                        detection_type="prompt_injection",
                        confidence=classifier_score,
                        rule_id="ONNX-001",
                    )

            return self._allow(start)
        except Exception as exc:
            if self.config.fail_open:
                return self._allow(start)
            raise FirewallEvaluationError("AI firewall evaluation failed closed") from exc

    def handle_block(self, decision: FirewallDecision) -> Response:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "type": "firewall_blocked",
                    "message": "Security policy violation. Request blocked.",
                    "mitre_atlas_id": decision.mitre_atlas_id,
                }
            },
        )

    def handle_error(self, _error: Exception) -> Response:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "firewall_error",
                    "message": "Security firewall failed closed.",
                }
            },
        )

    async def _block(
        self,
        start: float,
        detection_type: str,
        confidence: float,
        rule_id: str | None,
    ) -> FirewallDecision:
        event_type = EVENT_BY_DETECTION_TYPE.get(detection_type, "prompt_injection_blocked")
        mitre_atlas_id = self._atlas_id_for_event(event_type)
        audit_event = {
            "event_type": self._audit_event_name(detection_type),
            "detection_type": detection_type,
            "confidence": round(confidence, 4),
            "rule_id": rule_id,
            "mitre_atlas_id": mitre_atlas_id,
        }
        decision = FirewallDecision(
            action=FIREWALL_DECISIONS.BLOCK,
            confidence=confidence,
            detection_type=detection_type,
            mitre_atlas_id=mitre_atlas_id,
            latency_ms=self._elapsed_ms(start),
            event_type=event_type,
            audit_event=audit_event,
        )
        self.metrics.record(decision)
        await self._emit_audit(audit_event)
        return decision

    def _allow(self, start: float) -> FirewallDecision:
        decision = FirewallDecision(
            action=FIREWALL_DECISIONS.ALLOW,
            confidence=0.0,
            latency_ms=self._elapsed_ms(start),
        )
        self.metrics.record(decision)
        return decision

    def _needs_semantic_scan(
        self,
        structural_score: float,
        jailbreak_matches: list[dict[str, Any]],
        override_score: float,
    ) -> bool:
        if structural_score >= 0.3 or override_score >= 0.3:
            return True
        return any(match["confidence"] >= 0.3 for match in jailbreak_matches)

    def _atlas_id_for_event(self, event_type: str) -> str | None:
        mapping = self.mitre_map.get("atlas_mappings", {}).get(event_type, {})
        atlas_id = mapping.get("atlas_id")
        return str(atlas_id) if atlas_id else None

    def _audit_event_name(self, detection_type: str) -> str:
        if detection_type == "jailbreak":
            return "firewall_jailbreak_detected"
        if detection_type in {"prompt_injection", "semantic_injection"}:
            return "firewall_injection_detected"
        if detection_type in {"role_manipulation", "system_prompt_override", "model_theft_attempt"}:
            return "firewall_bypass_attempt"
        return "firewall_block"

    async def _emit_audit(self, event: dict[str, Any]) -> None:
        if self.audit_sink is None:
            return
        result = self.audit_sink(event)
        if hasattr(result, "__await__"):
            await result

    def _elapsed_ms(self, start: float) -> float:
        return round((time.perf_counter() - start) * 1000.0, 3)


class FirewallEvaluationError(RuntimeError):
    pass


def load_mitre_atlas_map(path: str) -> dict[str, Any]:
    atlas_path = Path(path)
    if not atlas_path.exists():
        return {"atlas_mappings": {}}
    raw = yaml.safe_load(atlas_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("MITRE ATLAS mapping must be a YAML object")
    return raw
