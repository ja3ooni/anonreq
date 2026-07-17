"""End-to-end round-trip integration tests for the AnonReq anonymization pipeline.

Verifies the FULL anonymization flow:
1. Request with PII → classification → detection → tokenization
2. Tokenized request → upstream provider (mocked via respx)
3. Provider response with tokens → restoration → original PII returned

Key invariant: raw PII must never cross the network boundary to the provider.
"""

from __future__ import annotations

import re

import httpx
import pytest
import respx
from unittest.mock import AsyncMock

from anonreq.classification.engine import ClassificationEngine
from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import PresidioClient
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.cleanup import CleanupStage
from anonreq.pipeline.classification import ClassificationStage
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.dlp import InboundDLPStage, OutboundDLPStage
from anonreq.pipeline.forwarding_guard import ForwardingGuard
from anonreq.pipeline.manager import PipelineManager
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.stages import SensitivityClassificationStage
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.pipeline.tool_governance import ToolGovernanceStage
from anonreq.tokenization.tokenizer import Tokenizer

PROVIDER_BASE_URL = "http://mock-provider.example"
PII_TEXT = "My name is John Smith, SSN 123-45-6789"
TENANT_ID = "default"
CONTEXT_ID = "e2e_session_001"
REQUEST_ID = "e2e_test_001"

TOKEN_PATTERN = re.compile(r"\[[A-Z][A-Z_]{0,49}_\d+\]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pipeline(cache_manager, presidio_client):
    """Build a minimal but complete anonymization pipeline for testing.

    Uses real stages where possible and skips policy/DLP/tool-governance
    (app_state=None → no-op).  This mirrors the real pipeline structure
    from ``build_pre_provider_pipeline`` + ``ProviderStage`` + post-stages
    without requiring config files on disk.
    """
    engine = ClassificationEngine(
        rules=[],
        default_action="ANONYMIZE",
    )

    manager = PipelineManager()
    manager.register(ClassificationStage(engine=engine))
    manager.register(DetectionStage(
        regex_detector=RegexDetector(),
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
    ))
    manager.register(SensitivityClassificationStage())
    manager.register(InboundDLPStage(app_state=None))
    manager.register(ToolGovernanceStage(app_state=None))
    manager.register(TokenizationStage(
        tokenizer=Tokenizer(),
        cache_manager=cache_manager,
    ))
    manager.register(ForwardingGuard())
    manager.register(ProviderStage(
        openai_base_url=PROVIDER_BASE_URL,
        api_key="test-api-key",
        timeout=5.0,
    ))
    manager.register(OutboundDLPStage(app_state=None))
    manager.register(RestorationStage())
    manager.register(CleanupStage(cache_manager=cache_manager))

    return manager


def _make_proc_ctx():
    """Create a ProcessingContext with PII in the request body."""
    return ProcessingContext(
        request_id=REQUEST_ID,
        tenant_id=TENANT_ID,
        context_id=CONTEXT_ID,
        original_request={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": PII_TEXT}],
            "stream": False,
        },
    )


def _mock_provider_response(content: str) -> dict:
    """Build a minimal OpenAI chat completion response."""
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """Full anonymization round-trip: PII → tokens → provider → restored PII."""

    @pytest.mark.asyncio
    async def test_pii_tokenized_before_provider(self, cache_manager):
        """Request body sent to the provider must contain tokens, NOT raw PII."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            route = respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json=_mock_provider_response(
                        "Hello [PERSON_N], your SSN is [US_SSN_M]"
                    ),
                ),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert not proc_ctx.has_errors(), f"Pipeline errors: {proc_ctx.errors}"
        assert route.called

        # Provider must NOT receive raw PII
        provider_body = route.calls[0].request.read()
        assert b"John Smith" not in provider_body
        assert b"123-45-6789" not in provider_body

        # Provider MUST receive tokens
        assert TOKEN_PATTERN.search(provider_body.decode())

    @pytest.mark.asyncio
    async def test_restored_response_contains_original_pii(self, cache_manager):
        """Response returned to the client must contain original PII, NOT tokens."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        def _echo_tokens_in_response(request):
            """Read tokens from the tokenized request and echo them back."""
            import json
            body = json.loads(request.content)
            content = body["messages"][0]["content"]
            tokens = TOKEN_PATTERN.findall(content)
            if tokens:
                response_text = (
                    "I see your name is " + tokens[0]
                    + " and your SSN is " + tokens[1]
                    + ". How can I help you today?"
                )
            else:
                response_text = "No tokens found"
            return httpx.Response(200, json=_mock_provider_response(response_text))

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                side_effect=_echo_tokens_in_response,
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert not proc_ctx.has_errors(), f"Pipeline errors: {proc_ctx.errors}"
        assert proc_ctx.restored_response is not None

        restored_content = proc_ctx.restored_response["choices"][0]["message"]["content"]

        # Must contain original PII
        assert "John Smith" in restored_content
        assert "123-45-6789" in restored_content

        # Must NOT contain residual tokens
        assert not TOKEN_PATTERN.search(restored_content), (
            f"Residual tokens in restored response: {restored_content}"
        )

    @pytest.mark.asyncio
    async def test_cache_mapping_cleaned_up(self, cache_manager):
        """Token mapping must be deleted from cache after successful round-trip."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json=_mock_provider_response("Response with [PERSON_N]"),
                ),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert not proc_ctx.has_errors()

        # Mapping must be deleted by CleanupStage
        remaining = await cache_manager.get_mapping(TENANT_ID, CONTEXT_ID)
        assert remaining == {}

    @pytest.mark.asyncio
    async def test_detections_include_both_regex_and_ner(self, cache_manager):
        """Detection finds SSN via regex and PERSON via mocked Presidio NER."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json=_mock_provider_response("safe response"),
                ),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert not proc_ctx.has_errors()
        assert proc_ctx.detections is not None

        entity_types = {d["entity_type"] for d in proc_ctx.detections}
        assert "US_SSN" in entity_types, "SSN should be detected by regex"
        assert "PERSON" in entity_types, "PERSON should be detected by mocked Presidio"

    @pytest.mark.asyncio
    async def test_token_mapping_matches_detections(self, cache_manager):
        """Token mappings in cache correspond 1-to-1 with detected entities."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json=_mock_provider_response("safe"),
                ),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert not proc_ctx.has_errors()
        assert proc_ctx.token_mappings is not None
        assert len(proc_ctx.token_mappings) >= 2

        # Each token maps to a non-empty original value
        for token, value in proc_ctx.token_mappings.items():
            assert TOKEN_PATTERN.match(token), f"Invalid token format: {token}"
            assert value, f"Empty value for token: {token}"

        # Original PII values are in the mapping
        values = set(proc_ctx.token_mappings.values())
        assert "John Smith" in values
        assert "123-45-6789" in values


class TestFailSecure:
    """Fail-secure behavior: provider errors must abort the pipeline cleanly."""

    @pytest.mark.asyncio
    async def test_provider_http_error_aborts_pipeline(self, cache_manager):
        """Provider returning HTTP 500 → pipeline aborts with 502 PipelineAbortError."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(
                    500, json={"error": {"message": "internal error"}}
                ),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        # Pipeline must have errors
        assert proc_ctx.has_errors()
        last_error = proc_ctx.errors[-1]
        assert isinstance(last_error, PipelineAbortError)
        assert last_error.status_code == 502

    @pytest.mark.asyncio
    async def test_no_restored_response_on_provider_error(self, cache_manager):
        """Provider error → no restored response (restoration stage never runs)."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(502, text="bad gateway"),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert proc_ctx.has_errors()
        assert proc_ctx.restored_response is None

    @pytest.mark.asyncio
    async def test_no_pii_in_error_path(self, cache_manager):
        """Even on error, no raw PII reaches the restored response or error message."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "upstream failure"}),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert proc_ctx.has_errors()

        # No restored response → no PII there
        assert proc_ctx.restored_response is None

        # Error message must be generic (no PII)
        error_msg = str(proc_ctx.errors[-1])
        assert "John Smith" not in error_msg
        assert "123-45-6789" not in error_msg

    @pytest.mark.asyncio
    async def test_tokenization_ran_before_provider_failure(self, cache_manager):
        """Token mapping exists in cache (tokenization ran) but restoration never did."""
        presidio_client = AsyncMock(spec=PresidioClient)
        presidio_client.analyze_text_nodes = AsyncMock(return_value=[
            [{"entity_type": "PERSON", "start": 11, "end": 21, "score": 0.95}],
        ])

        pipeline = _build_pipeline(cache_manager, presidio_client)
        proc_ctx = _make_proc_ctx()

        with respx.mock:
            respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "fail"}),
            )

            proc_ctx = await pipeline.run(proc_ctx)

        assert proc_ctx.has_errors()

        # Tokenization ran → mapping exists in cache
        mapping = await cache_manager.get_mapping(TENANT_ID, CONTEXT_ID)
        assert len(mapping) >= 2

        # Restoration never ran → mapping NOT cleaned up
        # (CleanupStage only runs after successful restoration)
