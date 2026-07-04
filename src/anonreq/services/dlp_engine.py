"""DLPEngine — inspects request text against core and custom DLP categories (Plan 13-01)."""

from __future__ import annotations

import re
from typing import Any

from anonreq.models.dlp import DLPCategory, DLPAction, DLPDetection, DLPResult
from anonreq.models.processing_context import ProcessingContext
from anonreq.models.classification import ClassificationLevel


class DLPEngine:
    """Core and custom Data Loss Prevention inspection engine."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize engine with category patterns from configuration."""
        self._core_patterns: dict[DLPCategory, list[dict[str, Any]]] = {}
        self._tenant_patterns: dict[str, list[dict[str, Any]]] = {}  # tenant_id -> patterns
        self._load_core_patterns(config.get("core_categories", {}))

    def _load_core_patterns(self, categories: dict[str, Any]) -> None:
        """Load and compile regex patterns for core categories."""
        for cat_name, cat_config in categories.items():
            try:
                category = DLPCategory(cat_name)
            except ValueError:
                # Silently skip custom or unknown categories at startup
                continue

            patterns = []
            for pattern in cat_config.get("patterns", []):
                try:
                    compiled = re.compile(pattern["regex"])
                    patterns.append({
                        "id": pattern["id"],
                        "regex": compiled,
                        "default_action": cat_config.get("default_action", "block"),
                    })
                except (re.error, KeyError):
                    continue
            self._core_patterns[category] = patterns

    async def inspect(
        self,
        text: str,
        tenant_id: str = "default",
        classification_level: ClassificationLevel | None = None,
    ) -> DLPResult:
        """Inspect text content for DLP violations across core and custom categories."""
        detections: list[DLPDetection] = []

        # Run core category patterns
        for category, patterns in self._core_patterns.items():
            for pattern in patterns:
                compiled: re.Pattern = pattern["regex"]
                for match in compiled.finditer(text):
                    detections.append(DLPDetection(
                        category=category,
                        action=DLPAction(pattern.get("default_action", "block")),
                        match_text=match.group(),
                        confidence=0.9,  # Regex exact match
                        start=match.start(),
                        end=match.end(),
                        pattern_id=pattern["id"],
                    ))

        # Run tenant custom patterns
        tenant_patterns = self._tenant_patterns.get(tenant_id, [])
        for pattern in tenant_patterns:
            compiled = pattern["regex"]
            for match in compiled.finditer(text):
                detections.append(DLPDetection(
                    category=DLPCategory(pattern["category"]),
                    action=DLPAction(pattern.get("action", "block")),
                    match_text=match.group(),
                    confidence=0.9,
                    start=match.start(),
                    end=match.end(),
                    pattern_id=pattern["id"],
                    is_custom_category=True,
                ))

        # Compute max action (most restrictive wins)
        max_action = self._compute_max_action(detections) if detections else DLPAction.ALLOW

        return DLPResult(
            tenant_id=tenant_id,
            detections=detections,
            max_action=max_action,
            is_blocked=max_action in (DLPAction.BLOCK, DLPAction.QUARANTINE),
            is_quarantined=max_action == DLPAction.QUARANTINE,
        )

    def _compute_max_action(self, detections: list[DLPDetection]) -> DLPAction:
        """Return most restrictive action based on rank: BLOCK > QUARANTINE > REDACT > ANONYMIZE > ALLOW."""
        action_rank = {
            DLPAction.ALLOW: 0,
            DLPAction.ANONYMIZE: 1,
            DLPAction.REDACT: 2,
            DLPAction.QUARANTINE: 3,
            DLPAction.BLOCK: 4,
        }
        return max((d.action for d in detections), key=lambda a: action_rank[a])

    def load_tenant_patterns(self, tenant_id: str, config: dict[str, Any]) -> None:
        """Load tenant custom patterns into memory (scopes patterns per tenant)."""
        patterns = []
        for pattern in config.get("patterns", []):
            try:
                compiled = re.compile(pattern["regex"])
                patterns.append({
                    "id": pattern["id"],
                    "regex": compiled,
                    "category": pattern["category"],
                    "action": pattern.get("action", "block"),
                })
            except (re.error, KeyError):
                continue
        self._tenant_patterns[tenant_id] = patterns

    async def inspect_request(self, ctx: ProcessingContext) -> DLPResult:
        """Helper to extract text nodes and run inspection."""
        text = self._extract_text(ctx)
        res_v2 = getattr(ctx, "classification_result_v2", None)
        classification = res_v2.highest if res_v2 else None
        return await self.inspect(text, ctx.tenant_id, classification)

    def _extract_text(self, ctx: ProcessingContext) -> str:
        """Safely extract all text node values from processing context."""
        texts = []
        for node in (ctx.text_nodes or []):
            if isinstance(node, dict):
                texts.append(node.get("value", ""))
            elif hasattr(node, "value"):
                texts.append(node.value)
            else:
                texts.append(str(node))
        return "\n".join(texts)
