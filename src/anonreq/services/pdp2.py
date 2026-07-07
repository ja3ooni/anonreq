from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anonreq.models.classification import ClassificationLevel
from anonreq.models.dlp import DLPAction, DLPResult
from anonreq.models.processing_context import ProcessingContext

ACTION_RANK = {
    DLPAction.ALLOW: 0,
    DLPAction.ANONYMIZE: 1,
    DLPAction.REDACT: 2,
    DLPAction.QUARANTINE: 3,
    DLPAction.BLOCK: 4,
}

CLASS_TO_DLP = {
    ClassificationLevel.PUBLIC: DLPAction.ALLOW,
    ClassificationLevel.INTERNAL: DLPAction.ALLOW,
    ClassificationLevel.CONFIDENTIAL: DLPAction.ANONYMIZE,
    ClassificationLevel.RESTRICTED: DLPAction.ANONYMIZE,
    ClassificationLevel.HIGHLY_RESTRICTED: DLPAction.BLOCK,
}

ACTION_TO_STATUS = {
    "ALLOW": 200,
    "ANONYMIZE": 200,
    "REDACT": 200,
    "QUARANTINE": 451,
    "BLOCK": 451,
}

ACTION_TO_AUDIT = {
    "ALLOW": "dlp_cleared",
    "ANONYMIZE": "dlp_anonymize",
    "REDACT": "dlp_redact",
    "QUARANTINE": "dlp_action_applied",
    "BLOCK": "dlp_action_applied",
}


@dataclass
class PolicyDecision:
    action: str
    status_code: int
    detail: str
    audit_event_type: str
    metadata_only: bool = False


class PDP2Service:
    def __init__(self, tenant_policies: dict[str, Any] | None = None) -> None:
        self._tenant_policies: dict[str, Any] = tenant_policies or {}

    def _tighten_action(self, base: DLPAction, constraint: DLPAction) -> DLPAction:
        if ACTION_RANK[constraint] > ACTION_RANK[base]:
            return constraint
        return base

    def _classification_to_dlp_action(self, level: ClassificationLevel) -> DLPAction:
        return CLASS_TO_DLP.get(level, DLPAction.ALLOW)

    async def evaluate(self, ctx: ProcessingContext) -> PolicyDecision:
        dlp_action = self._get_dlp_action(ctx)
        classification_action = self._get_classification_action(ctx)

        combined = self._tighten_action(dlp_action, classification_action)

        action_str = combined.value.upper()
        return PolicyDecision(
            action=action_str,
            status_code=ACTION_TO_STATUS.get(action_str, 200),
            detail=self._build_detail(action_str),
            audit_event_type=ACTION_TO_AUDIT.get(action_str, "dlp_cleared"),
            metadata_only=combined in (DLPAction.QUARANTINE, DLPAction.BLOCK),
        )

    def _get_dlp_action(self, ctx: ProcessingContext) -> DLPAction:
        if ctx.dlp_result is not None:
            return ctx.dlp_result.max_action
        return DLPAction.ALLOW

    def _get_classification_action(self, ctx: ProcessingContext) -> DLPAction:
        res_v2 = getattr(ctx, "classification_result_v2", None)
        if res_v2 is not None and hasattr(res_v2, "highest"):
            return self._classification_to_dlp_action(res_v2.highest)
        return DLPAction.ALLOW

    def _build_detail(self, action: str) -> str:
        if action in ("BLOCK", "QUARANTINE"):
            return f"Request {action.lower()}ed by policy"
        return "Allowed by policy"
