"""DLP pipeline integration tests (Plan 13-02).

Tests cover:
- Task 1: DLP integration into pipeline with correct execution order
- Task 2: PDP #2 DLP-aware contextual rule evaluation

Pipeline execution order:
  Threat -> Classification -> DLP (inbound) -> PDP #2
  -> Anonymize -> Forward -> Restore -> DLP (outbound)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.models.dlp import DLPAction, DLPCategory, DLPDetection, DLPResult
from anonreq.models.processing_context import ProcessingContext

# ===========================================================================
# Task 1: DLP Pipeline Integration
# ===========================================================================


class TestDLPPipelineIntegration:
    """PipelineService correctly integrates DLP in execution order."""

    @pytest.mark.asyncio
    async def test_dlp_result_stamped_on_context(self):
        """DLPEngine.inspect_request result is stamped on ctx.dlp_result."""
        from anonreq.services.pdp2 import PDP2Service
        from anonreq.services.pipeline import PipelineService

        dlp_engine = MagicMock()
        # Return a DLPResult with a BLOCK detection
        dlp_engine.inspect_request = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[
                DLPDetection(
                    category=DLPCategory.PII,
                    action=DLPAction.BLOCK,
                    match_text="john@example.com",
                    confidence=0.9,
                    start=0, end=15,
                    pattern_id="pii_email",
                ),
            ],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)

        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)
        ctx = ProcessingContext(request_id="test_001", tenant_id="default")
        ctx.text_nodes = [{"value": "Contact john@example.com"}]
        ctx.classification_result = {"action": "ANONYMIZE"}

        # Run inbound DLP directly
        await pipeline._run_inbound_dlp(ctx)

        assert ctx.dlp_result is not None
        assert ctx.dlp_result.is_blocked is True
        assert ctx.dlp_result.max_action == DLPAction.BLOCK
        dlp_engine.inspect_request.assert_awaited_once_with(ctx)

    @pytest.mark.asyncio
    async def test_dlp_block_aborts_pipeline_before_provider(self):
        """DLP BLOCK aborts pipeline — provider never called."""
        from anonreq.services.pdp2 import PDP2Service
        from anonreq.services.pipeline import PipelineService

        dlp_engine = MagicMock()
        dlp_engine.inspect.return_value = DLPResult(
            tenant_id="default",
            detections=[MagicMock()],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        )
        dlp_engine.inspect_request = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[MagicMock()],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)
        pdp2.evaluate = AsyncMock()

        # Mock the pre-DLP methods to succeed
        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)
        pipeline._run_threat_detection = AsyncMock()
        pipeline._run_extraction = AsyncMock()
        pipeline._run_detection = AsyncMock()
        pipeline._run_classification = AsyncMock()
        pipeline._run_anonymization = AsyncMock()
        pipeline._run_forward = AsyncMock()
        pipeline._run_restoration = AsyncMock()

        ctx = ProcessingContext(request_id="test_002", tenant_id="default")
        ctx.text_nodes = [{"value": "email: john@example.com"}]

        result = await pipeline.run(ctx)

        # DLP BLOCK -> pipeline has errors
        assert result.has_errors()
        from anonreq.exceptions import PipelineBlockedError

        assert isinstance(result.errors[-1], PipelineBlockedError)
        assert result.errors[-1].status_code == 451

        # PDP #2 should NOT have been called (DLP blocked before PDP #2)
        pdp2.evaluate.assert_not_awaited()

        # Provider should NOT have been called
        pipeline._run_anonymization.assert_not_awaited()
        pipeline._run_forward.assert_not_awaited()
        pipeline._run_restoration.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dlp_allowed_continues_to_pdp2(self):
        """DLP ALLOW continues pipeline to PDP #2."""
        from anonreq.services.pdp2 import PDP2Service, PolicyDecision
        from anonreq.services.pipeline import PipelineService

        dlp_engine = MagicMock()
        dlp_engine.inspect_request = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[],
            max_action=DLPAction.ALLOW,
            is_blocked=False,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)
        pdp2.evaluate = AsyncMock(return_value=PolicyDecision(
            action="ALLOW",
            status_code=200,
            detail="Allowed by policy",
            audit_event_type="dlp_cleared",
        ))

        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)
        pipeline._run_threat_detection = AsyncMock()
        pipeline._run_extraction = AsyncMock()
        pipeline._run_detection = AsyncMock()
        pipeline._run_classification = AsyncMock()
        pipeline._run_anonymization = AsyncMock()
        pipeline._run_forward = AsyncMock()
        pipeline._run_restoration = AsyncMock()
        pipeline._run_outbound_dlp = AsyncMock()

        ctx = ProcessingContext(request_id="test_003", tenant_id="default")
        ctx.text_nodes = [{"value": "How can I help?"}]

        result = await pipeline.run(ctx)

        # No errors — DLP allowed
        assert not result.has_errors()

        # PDP #2 should have been called
        pdp2.evaluate.assert_awaited_once_with(ctx)

        # Provider should have been called
        pipeline._run_anonymization.assert_awaited_once()
        pipeline._run_forward.assert_awaited_once()
        pipeline._run_restoration.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_outbound_dlp_scans_response_with_dual_gate(self):
        """Outbound DLP scans pre-restore + post-restore response text."""
        from anonreq.services.pdp2 import PDP2Service
        from anonreq.services.pipeline import PipelineService

        dlp_engine = MagicMock()
        dlp_engine.inspect = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[MagicMock()],
            max_action=DLPAction.ALLOW,
            is_blocked=False,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)

        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)
        ctx = ProcessingContext(request_id="test_004", tenant_id="default")
        ctx.provider_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "The SSN is 123-45-6789",
                    },
                },
            ],
        }

        await pipeline._run_outbound_dlp(ctx)

        # DLP engine should inspect the response text
        dlp_engine.inspect.assert_awaited_once()
        call_args = dlp_engine.inspect.call_args[0]
        assert "123-45-6789" in call_args[0]
        assert call_args[1] == "default"  # tenant_id

    @pytest.mark.asyncio
    async def test_outbound_dlp_block_suppresses_response(self):
        """Outbound DLP BLOCK results in error with 451."""
        from anonreq.services.pdp2 import PDP2Service, PolicyDecision
        from anonreq.services.pipeline import PipelineService

        dlp_engine = MagicMock()
        dlp_engine.inspect_request = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[],
            max_action=DLPAction.ALLOW,
            is_blocked=False,
            is_quarantined=False,
        ))
        dlp_engine.inspect = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[MagicMock()],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)
        pdp2.evaluate = AsyncMock(return_value=PolicyDecision(
            action="ALLOW",
            status_code=200,
            detail="Allowed",
            audit_event_type="dlp_cleared",
        ))

        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)
        pipeline._run_threat_detection = AsyncMock()
        pipeline._run_extraction = AsyncMock()
        pipeline._run_detection = AsyncMock()
        pipeline._run_classification = AsyncMock()
        pipeline._run_anonymization = AsyncMock()
        pipeline._run_forward = AsyncMock()
        pipeline._run_restoration = AsyncMock()

        ctx = ProcessingContext(request_id="test_005", tenant_id="default")
        ctx.text_nodes = [{"value": "How can I help?"}]
        ctx.provider_response = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "SSN: 123-45-6789"}}],  # noqa: E501
        }

        result = await pipeline.run(ctx)

        # Outbound DLP BLOCK -> pipeline has errors
        assert result.has_errors()
        from anonreq.exceptions import OutboundDLPError

        assert isinstance(result.errors[-1], OutboundDLPError)
        assert result.errors[-1].status_code == 451

    @pytest.mark.asyncio
    async def test_dlp_execution_order_after_classification_before_pdp2(self):
        """DLP runs after classification, before PDP #2 in pipeline execution."""
        from anonreq.services.pdp2 import PDP2Service, PolicyDecision
        from anonreq.services.pipeline import PipelineService

        call_order: list[str] = []

        dlp_engine = MagicMock()
        dlp_engine.inspect_request = AsyncMock(return_value=DLPResult(
            tenant_id="default",
            detections=[],
            max_action=DLPAction.ALLOW,
            is_blocked=False,
            is_quarantined=False,
        ))

        pdp2 = MagicMock(spec=PDP2Service)
        pdp2.evaluate = AsyncMock(return_value=PolicyDecision(
            action="ALLOW", status_code=200, detail="Allowed", audit_event_type="dlp_cleared",
        ))

        pipeline = PipelineService(dlp_engine=dlp_engine, pdp2_service=pdp2)

        # Use spies to track call order
        pipeline._run_threat_detection = AsyncMock(side_effect=lambda _ctx: call_order.append("threat"))  # noqa: E501
        pipeline._run_extraction = AsyncMock(side_effect=lambda _ctx: call_order.append("extraction"))  # noqa: E501
        pipeline._run_detection = AsyncMock(side_effect=lambda _ctx: call_order.append("detection"))
        pipeline._run_classification = AsyncMock(side_effect=lambda _ctx: call_order.append("classification"))  # noqa: E501
        # Override _run_inbound_dlp to track order
        original_inbound_dlp = pipeline._run_inbound_dlp

        async def tracked_inbound_dlp(ctx):
            call_order.append("dlp_inbound")
            await original_inbound_dlp(ctx)

        pipeline._run_inbound_dlp = tracked_inbound_dlp
        pipeline._run_anonymization = AsyncMock(side_effect=lambda _ctx: call_order.append("anonymize"))  # noqa: E501
        pipeline._run_forward = AsyncMock(side_effect=lambda _ctx: call_order.append("forward"))
        pipeline._run_restoration = AsyncMock(side_effect=lambda _ctx: call_order.append("restore"))
        pipeline._run_outbound_dlp = AsyncMock(side_effect=lambda _ctx: call_order.append("dlp_outbound"))  # noqa: E501

        ctx = ProcessingContext(request_id="test_006", tenant_id="default")
        ctx.text_nodes = [{"value": "Hello"}]

        await pipeline.run(ctx)

        # Verify execution order
        assert call_order == [
            "threat",
            "extraction",
            "detection",
            "classification",
            "dlp_inbound",
            "anonymize",
            "forward",
            "restore",
            "dlp_outbound",
        ], f"Unexpected call order: {call_order}"


# ===========================================================================
# Task 2: PDP #2 DLP-Aware Evaluation
# ===========================================================================


class TestPDP2DLPIntegration:
    """PDP2Service integrates DLP results with classification for contextual rules."""

    def test_tighten_action_never_loosens(self):
        """_tighten_action returns more restrictive of base and constraint."""
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()

        # BLOCK > ANONYMIZE -> stays BLOCK
        result = pdp2._tighten_action(DLPAction.BLOCK, DLPAction.ANONYMIZE)
        assert result == DLPAction.BLOCK

        # ALLOW + BLOCK -> BLOCK (tighten)
        result = pdp2._tighten_action(DLPAction.ALLOW, DLPAction.BLOCK)
        assert result == DLPAction.BLOCK

        # BLOCK + ALLOW -> BLOCK (never loosens)
        result = pdp2._tighten_action(DLPAction.BLOCK, DLPAction.ALLOW)
        assert result == DLPAction.BLOCK

        # ANONYMIZE + REDACT -> REDACT
        result = pdp2._tighten_action(DLPAction.ANONYMIZE, DLPAction.REDACT)
        assert result == DLPAction.REDACT

        # Same action -> same
        result = pdp2._tighten_action(DLPAction.QUARANTINE, DLPAction.QUARANTINE)
        assert result == DLPAction.QUARANTINE

    def test_classification_to_dlp_action_mapping(self):
        """Classification levels map to expected DLP actions."""
        from anonreq.models.classification import ClassificationLevel
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()

        assert pdp2._classification_to_dlp_action(ClassificationLevel.PUBLIC) == DLPAction.ALLOW
        assert pdp2._classification_to_dlp_action(ClassificationLevel.INTERNAL) == DLPAction.ALLOW
        assert pdp2._classification_to_dlp_action(ClassificationLevel.CONFIDENTIAL) == DLPAction.ANONYMIZE  # noqa: E501
        assert pdp2._classification_to_dlp_action(ClassificationLevel.RESTRICTED) == DLPAction.ANONYMIZE  # noqa: E501
        assert pdp2._classification_to_dlp_action(ClassificationLevel.HIGHLY_RESTRICTED) == DLPAction.BLOCK  # noqa: E501

    @pytest.mark.asyncio
    async def test_pdp2_evaluate_with_dlp_block(self):
        """PDP #2 returns BLOCK when DLP result is BLOCK."""
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_010", tenant_id="default")
        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[DLPDetection(
                category=DLPCategory.PII, action=DLPAction.BLOCK,
                match_text="test", confidence=0.9, start=0, end=4,
                pattern_id="test",
            )],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        )

        decision = await pdp2.evaluate(ctx)
        assert decision.action == "BLOCK"
        assert decision.status_code == 451
        assert decision.audit_event_type == "dlp_action_applied"

    @pytest.mark.asyncio
    async def test_category_wins_determines_base_action(self):
        """DLP detection category determines the base action."""
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_011", tenant_id="default")

        # PII detection with QUARANTINE
        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[DLPDetection(
                category=DLPCategory.INTELLECTUAL_PROPERTY, action=DLPAction.QUARANTINE,
                match_text="trade secret", confidence=0.9, start=0, end=12,
                pattern_id="ip_trade_secret",
            )],
            max_action=DLPAction.QUARANTINE,
            is_blocked=True,
            is_quarantined=True,
        )

        decision = await pdp2.evaluate(ctx)
        assert decision.action == "QUARANTINE"
        assert decision.metadata_only is True

    @pytest.mark.asyncio
    async def test_classification_tightens_when_more_restrictive(self):
        """Classification level tightens DLP action when more restrictive."""
        from anonreq.models.classification import ClassificationLevel, ClassificationResult
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_012", tenant_id="default")

        # DLP says ALLOW (no detections), but classification says HIGHLY_RESTRICTED
        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[],
            max_action=DLPAction.ALLOW,
            is_blocked=False,
            is_quarantined=False,
        )

        # Set classification_result_v2
        ctx.classification_result_v2 = ClassificationResult(
            highest=ClassificationLevel.HIGHLY_RESTRICTED,
            labels=["API_KEY"],
            detected_levels=[ClassificationLevel.HIGHLY_RESTRICTED],
        )

        decision = await pdp2.evaluate(ctx)
        # DLP ALLOW + HIGHLY_RESTRICTED (BLOCK) -> BLOCK (tightened)
        assert decision.action == "BLOCK"
        assert decision.status_code == 451

    @pytest.mark.asyncio
    async def test_classification_never_loosens_dlp(self):
        """Classification tightening never loosens a more restrictive DLP action."""
        from anonreq.models.classification import ClassificationLevel, ClassificationResult
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_013", tenant_id="default")

        # DLP says BLOCK (PII detected)
        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[DLPDetection(
                category=DLPCategory.PII, action=DLPAction.BLOCK,
                match_text="ssn", confidence=0.9, start=0, end=3,
                pattern_id="pii_ssn",
            )],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        )

        # Classification says PUBLIC (least restrictive)
        ctx.classification_result_v2 = ClassificationResult(
            highest=ClassificationLevel.PUBLIC,
            labels=["PERSON"],
            detected_levels=[ClassificationLevel.PUBLIC],
        )

        decision = await pdp2.evaluate(ctx)
        # DLP BLOCK + PUBLIC (ALLOW) -> BLOCK (never loosens)
        assert decision.action == "BLOCK"

    @pytest.mark.asyncio
    async def test_no_dlp_no_classification_allows(self):
        """No DLP detections and no classification -> ALLOW."""
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_014", tenant_id="default")
        # No dlp_result, no classification_result_v2

        decision = await pdp2.evaluate(ctx)
        assert decision.action == "ALLOW"
        assert decision.status_code == 200
        assert decision.audit_event_type == "dlp_cleared"

    @pytest.mark.asyncio
    async def test_most_restrictive_action_wins_across_sources(self):
        """Most restrictive action across DLP + classification wins."""
        from anonreq.models.classification import ClassificationLevel, ClassificationResult
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_015", tenant_id="default")

        # DLP says ANONYMIZE (source code detected)
        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[DLPDetection(
                category=DLPCategory.SOURCE_CODE, action=DLPAction.ANONYMIZE,
                match_text="api_key", confidence=0.9, start=0, end=7,
                pattern_id="sc_api_key",
            )],
            max_action=DLPAction.ANONYMIZE,
            is_blocked=False,
            is_quarantined=False,
        )

        # Classification says RESTRICTED -> ANONYMIZE
        ctx.classification_result_v2 = ClassificationResult(
            highest=ClassificationLevel.RESTRICTED,
            labels=["CREDIT_CARD"],
            detected_levels=[ClassificationLevel.RESTRICTED],
        )

        decision = await pdp2.evaluate(ctx)
        # Both say ANONYMIZE -> ANONYMIZE
        assert decision.action == "ANONYMIZE"
        assert decision.status_code == 200

    @pytest.mark.asyncio
    async def test_dlp_anonymize_action_allows_pipeline(self):
        """PDP #2 returns ANONYMIZE action with 200 status."""
        from anonreq.services.pdp2 import PDP2Service

        pdp2 = PDP2Service()
        ctx = ProcessingContext(request_id="test_016", tenant_id="default")

        ctx.dlp_result = DLPResult(
            tenant_id="default",
            detections=[DLPDetection(
                category=DLPCategory.SOURCE_CODE, action=DLPAction.ANONYMIZE,
                match_text="secret_key", confidence=0.9, start=0, end=10,
                pattern_id="sc_api_key",
            )],
            max_action=DLPAction.ANONYMIZE,
            is_blocked=False,
            is_quarantined=False,
        )

        decision = await pdp2.evaluate(ctx)
        assert decision.action == "ANONYMIZE"
        assert decision.status_code == 200
