"""Integration tests for DLP pipeline stages registered in the runtime pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.exceptions import OutboundDLPError, PipelineBlockedError
from anonreq.models.dlp import DLPAction, DLPDetection, DLPResult
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.manager import PipelineManager


class TestRuntimeDLPPipeline:
    """Tests that the runtime pipeline correctly includes and executes DLP stages."""

    @pytest.mark.asyncio
    async def test_pipeline_manager_includes_dlp_stages(self):
        """A PipelineManager built by build_pipeline() includes InboundDLPStage and OutboundDLPStage."""
        from anonreq.routing.chat import build_pipeline

        mock_cache = MagicMock()
        mock_presidio = MagicMock()
        mock_app_state = MagicMock()
        mock_app_state.dlp_engine = MagicMock()

        pm = build_pipeline(
            cache_manager=mock_cache,
            presidio_client=mock_presidio,
            app_state=mock_app_state,
        )

        stage_names = [s.name for s in pm.stages]
        assert "InboundDLPStage" in stage_names
        assert "OutboundDLPStage" in stage_names

        # Verify ordering: InboundDLPStage before ForwardingGuard,
        # OutboundDLPStage after ProviderStage
        assert stage_names.index("InboundDLPStage") < stage_names.index("ForwardingGuard")
        assert stage_names.index("OutboundDLPStage") > stage_names.index("ProviderStage")

    @pytest.mark.asyncio
    async def test_inbound_dlp_block_calls_fail_secure(self):
        """An inbound DLP block recorded on ctx.dlp_result calls ctx.fail_secure()."""
        from anonreq.pipeline.dlp import InboundDLPStage

        dlp_engine = AsyncMock()
        dlp_engine.inspect_request.return_value = DLPResult(
            tenant_id="default",
            detections=[
                DLPDetection(
                    category="PII",
                    action=DLPAction.BLOCK,
                    match_text="secret",
                    confidence=0.99,
                    start=0,
                    end=6,
                    pattern_id="test",
                )
            ],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        )

        app_state = MagicMock()
        app_state.dlp_engine = dlp_engine

        stage = InboundDLPStage(app_state=app_state)
        ctx = ProcessingContext(request_id="test_001", tenant_id="default")
        ctx.text_nodes = [{"value": "my secret is here"}]
        ctx = await stage.execute(ctx)

        assert ctx.dlp_result is not None
        assert ctx.dlp_result.is_blocked is True
        assert ctx.has_errors()
        assert isinstance(ctx.errors[-1], PipelineBlockedError)

    @pytest.mark.asyncio
    async def test_outbound_dlp_block_prevents_restored_response(self):
        """An outbound DLP block prevents restored response delivery."""
        from anonreq.pipeline.dlp import OutboundDLPStage

        dlp_engine = AsyncMock()
        dlp_engine.inspect.return_value = DLPResult(
            tenant_id="default",
            detections=[],
            max_action=DLPAction.BLOCK,
            is_blocked=True,
            is_quarantined=False,
        )

        app_state = MagicMock()
        app_state.dlp_engine = dlp_engine

        stage = OutboundDLPStage(app_state=app_state)
        ctx = ProcessingContext(request_id="test_002", tenant_id="default")
        ctx.provider_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Confidential data leaked here",
                    },
                },
            ],
        }

        ctx = await stage.execute(ctx)

        assert ctx.outbound_dlp_result is not None
        assert ctx.outbound_dlp_result.is_blocked is True
        assert ctx.has_errors()
        assert isinstance(ctx.errors[-1], OutboundDLPError)
