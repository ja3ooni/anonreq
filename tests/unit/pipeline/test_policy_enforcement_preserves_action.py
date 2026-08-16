"""PolicyEnforcementStage must not wipe classification action."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from anonreq.models.classification import ClassificationLevel, ClassificationResult
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.stages import PolicyEnforcementStage
from anonreq.policy.models import PolicyAction, PolicyDecision
from anonreq.policy.pep import PolicyEnforcementResult


@pytest.mark.asyncio
async def test_policy_enforcement_preserves_anonymize_action() -> None:
    decision = PolicyDecision(
        action=PolicyAction.ALLOW,
        matched_rule_ids=[],
        decision_ts=datetime.now(UTC),
    )
    pdp = AsyncMock()
    pdp.evaluate_all = AsyncMock(return_value=decision)
    pep = AsyncMock()
    pep.enforce = AsyncMock(
        return_value=PolicyEnforcementResult(
            action=PolicyAction.ALLOW,
            should_forward=True,
            status_code=200,
        ),
    )
    stage = PolicyEnforcementStage(app_state=SimpleNamespace(pdp=pdp, pep=pep))

    ctx = ProcessingContext(request_id="req_test", tenant_id="default")
    ctx.classification_result = {
        "action": "ANONYMIZE",
        "matched_rule_ids": ["CLS-005"],
    }
    ctx.classification_result_v2 = ClassificationResult(
        highest=ClassificationLevel.INTERNAL,
        labels=["IBAN_DE"],
        detected_levels=[ClassificationLevel.INTERNAL],
        highest_entity="IBAN_DE",
    )

    await stage.execute(ctx)

    assert ctx.classification_result["action"] == "ANONYMIZE"
    assert ctx.classification_result["matched_rule_ids"] == ["CLS-005"]
    assert ctx.classification_result["classification_level"] == "INTERNAL"
    assert ctx.classification_result["highest_entity"] == "IBAN_DE"
