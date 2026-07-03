from __future__ import annotations

import re
from typing import Any

from anonreq.firewall.models import (
    DetectionCategory,
    DetectionResult,
    FirewallAction,
    FirewallRule,
    RuleCategoryConfig,
    SeverityActionMapping,
    SeverityLevel,
)


_SEVERITY_ORDER: dict[SeverityLevel, int] = {
    SeverityLevel.HIGH: 3,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.LOW: 1,
}


class FirewallRuleEngine:
    def __init__(
        self,
        rules: list[FirewallRule],
        category_config: dict[str, RuleCategoryConfig] | None = None,
        severity_mapping: SeverityActionMapping | None = None,
    ) -> None:
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        self._category_config: dict[str, RuleCategoryConfig] = {}
        if category_config:
            self._category_config = {k: v for k, v in category_config.items()}
        self._severity_mapping = severity_mapping or SeverityActionMapping()

    async def evaluate(self, text: str) -> list[DetectionResult]:
        results: list[DetectionResult] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            cat_name = rule.category.value
            cat_cfg = self._category_config.get(cat_name)
            if cat_cfg is not None and not cat_cfg.enabled:
                continue

            if rule.pattern is None:
                continue

            matched, confidence = self._match_rule(rule, text)
            if not matched:
                continue

            threshold = cat_cfg.threshold if cat_cfg is not None else 0.85
            if confidence < threshold:
                continue

            snippet = self._make_snippet(text, rule)

            results.append(
                DetectionResult(
                    category=rule.category,
                    confidence=confidence,
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    action=rule.action,
                    matched_text_snippet=snippet,
                )
            )

        return self._deduplicate_by_category(results)

    async def evaluate_with_ml(
        self,
        text: str,
        ml_model: Any,
    ) -> list[DetectionResult]:
        rule_results = await self.evaluate(text)

        if not rule_results:
            return []

        try:
            ml_results = await ml_model.predict(text)
        except Exception:
            return rule_results

        return self._merge_results(rule_results, ml_results)

    def _match_rule(self, rule: FirewallRule, text: str) -> tuple[bool, float]:
        if rule.pattern is None:
            return False, 0.0
        try:
            compiled = re.compile(rule.pattern)
            match = compiled.search(text)
            if match:
                match_len = len(match.group(0))
                score = min(1.0, match_len / 100.0 + 0.8)
                return True, score
            return False, 0.0
        except re.error:
            return False, 0.0

    def _make_snippet(self, text: str, rule: FirewallRule) -> str | None:
        if rule.pattern is None:
            return None
        try:
            compiled = re.compile(rule.pattern)
            match = compiled.search(text)
            if match:
                snippet = match.group(0)
                if len(snippet) > 50:
                    snippet = snippet[:50]
                return snippet
            return None
        except re.error:
            return None

    def _deduplicate_by_category(self, results: list[DetectionResult]) -> list[DetectionResult]:
        best: dict[DetectionCategory, DetectionResult] = {}
        for result in results:
            existing = best.get(result.category)
            if existing is None or self._severity_score(result.severity) > self._severity_score(
                existing.severity
            ):
                best[result.category] = result
        return list(best.values())

    def _merge_results(
        self,
        rule_results: list[DetectionResult],
        ml_results: list[DetectionResult],
    ) -> list[DetectionResult]:
        merged: dict[DetectionCategory, DetectionResult] = {}

        for r in rule_results:
            merged[r.category] = r

        for m in ml_results:
            existing = merged.get(m.category)
            if existing is None or m.confidence > existing.confidence:
                merged[m.category] = m

        return list(merged.values())

    def _severity_score(self, severity: SeverityLevel) -> int:
        return _SEVERITY_ORDER.get(severity, 0)
