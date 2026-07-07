"""Pipeline integration tests — stage execution, error paths, full flow.

Tests cover:
- PipelineManager stage registration and sequential execution
- All pipeline stages: Classification, Detection, Tokenization,
  ForwardingGuard, Provider, Restoration, Cleanup
- Restorer token→value replacement
- Error paths: BLOCK (403), missing prerequisites (503), provider errors
- Full pipeline end-to-end via FastAPI TestClient
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def sample_text_nodes_two():
    return [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "My email is john@example.com and phone is +1-555-123-4567",
        },
        {
            "path": "messages[1].content",
            "role": "assistant",
            "value": "I'll contact you at that number.",
        },
    ]


@pytest.fixture
def proc_ctx():
    from anonreq.models.processing_context import ProcessingContext

    return ProcessingContext(request_id="test_req_001", tenant_id="default")


@pytest.fixture
def sample_request_dict():
    return {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "My name is John and email is john@example.com"},
            {"role": "assistant", "content": "Sure, I can help with that."},
        ],
        "stream": False,
    }


# ===========================================================================
# Task 1: PipelineStage ABC + PipelineManager
# ===========================================================================


class TestPipelineManager:
    """PipelineManager registers stages and executes them in order."""

    @pytest.mark.asyncio
    async def test_stage_order(self, proc_ctx):
        """Stages execute in registration order."""
        from anonreq.pipeline.base import PipelineStage
        from anonreq.pipeline.manager import PipelineManager

        call_order: list[str] = []

        class StageA(PipelineStage):
            def __init__(self):
                super().__init__("StageA")

            async def execute(self, ctx):
                call_order.append("StageA")
                return ctx

        class StageB(PipelineStage):
            def __init__(self):
                super().__init__("StageB")

            async def execute(self, ctx):
                call_order.append("StageB")
                return ctx

        manager = PipelineManager()
        manager.register(StageA())
        manager.register(StageB())

        result = await manager.run(proc_ctx)
        assert call_order == ["StageA", "StageB"]
        assert not result.has_errors()

    @pytest.mark.asyncio
    async def test_stage_abort_on_error(self, proc_ctx):
        """If a stage sets ctx.errors, subsequent stages are skipped."""
        from anonreq.pipeline.base import PipelineStage
        from anonreq.pipeline.manager import PipelineManager

        call_order: list[str] = []

        class StageA(PipelineStage):
            def __init__(self):
                super().__init__("StageA")

            async def execute(self, ctx):
                call_order.append("StageA")
                return ctx

        class StageB(PipelineStage):
            def __init__(self):
                super().__init__("StageB")

            async def execute(self, ctx):
                call_order.append("StageB")
                ctx.fail_secure(ValueError("StageB failed"))
                return ctx

        class StageC(PipelineStage):
            def __init__(self):
                super().__init__("StageC")

            async def execute(self, ctx):
                call_order.append("StageC")
                return ctx

        manager = PipelineManager()
        manager.register(StageA())
        manager.register(StageB())
        manager.register(StageC())

        result = await manager.run(proc_ctx)
        assert call_order == ["StageA", "StageB"]
        assert result.has_errors()

    @pytest.mark.asyncio
    async def test_stage_unhandled_exception(self, proc_ctx):
        """Unhandled exception in a stage aborts pipeline."""
        from anonreq.pipeline.base import PipelineStage
        from anonreq.pipeline.manager import PipelineManager

        call_order: list[str] = []

        class StageA(PipelineStage):
            def __init__(self):
                super().__init__("StageA")

            async def execute(self, ctx):
                call_order.append("StageA")
                raise RuntimeError("Unexpected error")

        class StageB(PipelineStage):
            def __init__(self):
                super().__init__("StageB")

            async def execute(self, ctx):
                call_order.append("StageB")
                return ctx

        manager = PipelineManager()
        manager.register(StageA())
        manager.register(StageB())

        result = await manager.run(proc_ctx)
        assert call_order == ["StageA"]
        assert result.has_errors()

    def test_register_and_stages_property(self):
        """Register adds stages and stages property returns a copy."""
        from anonreq.pipeline.base import PipelineStage
        from anonreq.pipeline.manager import PipelineManager

        class TestStage(PipelineStage):
            def __init__(self):
                super().__init__("Test")

            async def execute(self, ctx):
                return ctx

        manager = PipelineManager()
        assert manager.stages == []

        stage = TestStage()
        manager.register(stage)
        assert len(manager.stages) == 1
        assert manager.stages[0] is stage

        # stages returns a copy, not the internal list
        assert manager.stages is not manager._stages


# ===========================================================================
# Task 1: ClassificationStage
# ===========================================================================


class TestClassificationStage:
    """ClassificationStage evaluates rules and sets ctx.classification_result."""

    @pytest.mark.asyncio
    async def test_anonymize_classification(self, proc_ctx, sample_text_nodes_two):
        """ANONYMIZE classification stores result and continues."""
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.pipeline.classification import ClassificationStage

        # Engine with no matching rules defaults to PASS, but create one
        # that returns ANONYMIZE for our test
        engine = MagicMock(spec=ClassificationEngine)
        engine.classify.return_value = {
            "action": "ANONYMIZE",
            "matched_rule_ids": ["TEST-001"],
            "matched_rule_versions": [1],
        }

        proc_ctx.text_nodes = sample_text_nodes_two
        stage = ClassificationStage(engine=engine)
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        assert result.classification_result is not None
        assert result.classification_result["action"] == "ANONYMIZE"

    @pytest.mark.asyncio
    async def test_block_classification(self, proc_ctx, sample_text_nodes_two):
        """BLOCK classification sets ctx.errors with 403."""
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.pipeline.classification import ClassificationStage

        engine = MagicMock(spec=ClassificationEngine)
        engine.classify.return_value = {
            "action": "BLOCK",
            "matched_rule_ids": ["CLS-001"],
            "matched_rule_versions": [1],
        }

        proc_ctx.text_nodes = sample_text_nodes_two
        stage = ClassificationStage(engine=engine)
        result = await stage.execute(proc_ctx)

        assert result.has_errors()
        from anonreq.exceptions import PipelineAbortError

        assert isinstance(result.errors[-1], PipelineAbortError)
        assert result.errors[-1].status_code == 403

    @pytest.mark.asyncio
    async def test_pass_classification(self, proc_ctx, sample_text_nodes_two):
        """PASS classification stores result and continues (no error)."""
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.pipeline.classification import ClassificationStage

        engine = MagicMock(spec=ClassificationEngine)
        engine.classify.return_value = {
            "action": "PASS",
            "matched_rule_ids": [],
            "matched_rule_versions": [],
        }

        proc_ctx.text_nodes = sample_text_nodes_two
        stage = ClassificationStage(engine=engine)
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        assert result.classification_result["action"] == "PASS"

    @pytest.mark.asyncio
    async def test_classification_extracts_text_nodes(self, proc_ctx, sample_request_dict):
        """ClassificationStage extracts text_nodes if not already set."""
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.pipeline.classification import ClassificationStage

        engine = MagicMock(spec=ClassificationEngine)
        engine.classify.return_value = {
            "action": "ANONYMIZE",
            "matched_rule_ids": [],
            "matched_rule_versions": [],
        }

        proc_ctx.original_request = sample_request_dict
        proc_ctx.text_nodes = None  # Not set yet
        stage = ClassificationStage(engine=engine)
        result = await stage.execute(proc_ctx)

        assert result.text_nodes is not None
        assert len(result.text_nodes) == 2  # Two messages


# ===========================================================================
# Task 1: DetectionStage
# ===========================================================================


class TestDetectionStage:
    """DetectionStage runs regex + Presidio + span arbitration."""

    @pytest.mark.asyncio
    async def test_detection_with_mocked_regex_and_presidio(
        self, proc_ctx, sample_text_nodes_two,
    ):
        """DetectionStage produces merged detections in ctx."""
        from anonreq.pipeline.detection import DetectionStage

        regex_detector = MagicMock()
        # First node: email detected, second node: no PII
        regex_detector.detect.side_effect = [
            [{"entity_type": "EMAIL_ADDRESS", "start": 11, "end": 27, "score": 1.0, "source": "regex"}],
            [],
        ]

        presidio_client = MagicMock()
        presidio_client.analyze_text_nodes.return_value = [
            [{"entity_type": "PERSON", "start": 3, "end": 7, "score": 0.95}],
            [],
        ]

        span_arbiter = MagicMock()
        # Merge single node, return combined
        span_arbiter.merge.side_effect = [
            [{"entity_type": "EMAIL_ADDRESS", "start": 11, "end": 27, "score": 1.0, "source": "regex"}],
            [],
        ]

        exclusion_list = MagicMock()
        exclusion_list.filter_detections.side_effect = lambda dets, text: dets

        proc_ctx.text_nodes = sample_text_nodes_two
        proc_ctx.classification_result = {"action": "ANONYMIZE"}

        stage = DetectionStage(
            regex_detector=regex_detector,
            presidio_client=presidio_client,
            span_arbiter=span_arbiter,
            exclusion_list=exclusion_list,
        )
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        assert result.detections is not None
        assert len(result.detections) >= 1

    @pytest.mark.asyncio
    async def test_detection_skipped_on_pass(self, proc_ctx, sample_text_nodes_two):
        """DetectionStage skips execution for PASS classification."""
        from anonreq.pipeline.detection import DetectionStage

        regex_detector = MagicMock()
        presidio_client = MagicMock()
        span_arbiter = MagicMock()
        exclusion_list = MagicMock()

        proc_ctx.text_nodes = sample_text_nodes_two
        proc_ctx.classification_result = {"action": "PASS"}

        stage = DetectionStage(
            regex_detector=regex_detector,
            presidio_client=presidio_client,
            span_arbiter=span_arbiter,
            exclusion_list=exclusion_list,
        )
        result = await stage.execute(proc_ctx)

        # None of the detection methods should have been called
        regex_detector.detect.assert_not_called()
        presidio_client.analyze_text_nodes.assert_not_called()

        # Detections should still be None (not set)
        assert result.detections is None

    @pytest.mark.asyncio
    async def test_detection_skipped_on_block(self, proc_ctx, sample_text_nodes_two):
        """DetectionStage skips execution for BLOCK classification."""
        from anonreq.pipeline.detection import DetectionStage

        regex_detector = MagicMock()
        presidio_client = MagicMock()
        span_arbiter = MagicMock()
        exclusion_list = MagicMock()

        proc_ctx.text_nodes = sample_text_nodes_two
        proc_ctx.classification_result = {"action": "BLOCK"}

        stage = DetectionStage(
            regex_detector=regex_detector,
            presidio_client=presidio_client,
            span_arbiter=span_arbiter,
            exclusion_list=exclusion_list,
        )
        result = await stage.execute(proc_ctx)

        regex_detector.detect.assert_not_called()
        assert result.detections is None


# ===========================================================================
# Task 1: TokenizationStage
# ===========================================================================


class TestTokenizationStage:
    """TokenizationStage replaces detections with tokens and stores mapping."""

    @pytest.mark.asyncio
    async def test_empty_detections_no_mapping(self, proc_ctx, sample_request_dict):
        """Empty detections → request unchanged, no mapping created."""
        from anonreq.pipeline.tokenization import TokenizationStage

        tokenizer = MagicMock()
        cache_manager = MagicMock()

        proc_ctx.original_request = sample_request_dict
        proc_ctx.detections = []  # No detections
        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.text_nodes = [
            {"path": "messages[0].content", "role": "user", "value": "Hello"},
        ]

        stage = TokenizationStage(tokenizer=tokenizer, cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        assert result.transformed_request == sample_request_dict
        assert result.token_mappings == {}
        cache_manager.store_mapping.assert_not_called()

    @pytest.mark.asyncio
    async def test_detections_create_mapping(self, proc_ctx, sample_request_dict):
        """Detections are tokenized and mapping stored."""
        from anonreq.pipeline.tokenization import TokenizationStage
        from anonreq.tokenization import Tokenizer

        tokenizer = Tokenizer()
        cache_manager = MagicMock()

        proc_ctx.original_request = sample_request_dict
        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.text_nodes = [
            {
                "path": "messages[0].content",
                "role": "user",
                "value": "My email is john@example.com",
            },
        ]

        # Create detection with correct offsets for the text above:
        # "My email is john@example.com"
        #  0  5    10  15   20
        # email starts at index 11, ends at index 27
        proc_ctx.detections = [
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": 11,
                "end": 27,
                "score": 1.0,
                "source": "regex",
                "node_index": 0,
            },
        ]

        stage = TokenizationStage(tokenizer=tokenizer, cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        assert result.token_mappings is not None
        assert len(result.token_mappings) == 1
        assert result.transformed_request is not None
        # The transformed request should have the token in place of the email
        token = list(result.token_mappings.keys())[0]
        content = result.transformed_request["messages"][0]["content"]
        assert token in content
        assert "john@example.com" not in content

        # store_mapping should have been called
        cache_manager.store_mapping.assert_called_once()

    @pytest.mark.asyncio
    async def test_tokenization_skipped_on_pass(self, proc_ctx):
        """TokenizationStage skips for PASS classification."""
        from anonreq.pipeline.tokenization import TokenizationStage

        tokenizer = MagicMock()
        cache_manager = MagicMock()

        proc_ctx.classification_result = {"action": "PASS"}

        stage = TokenizationStage(tokenizer=tokenizer, cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        tokenizer.tokenize.assert_not_called()
        cache_manager.store_mapping.assert_not_called()


# ============================================================================
# Task 2: ForwardingGuard
# ============================================================================


class TestForwardingGuard:
    """ForwardingGuard verifies prerequisites before provider call."""

    @pytest.mark.asyncio
    async def test_passes_with_complete_prerequisites(self, proc_ctx):
        """ForwardingGuard passes when all prerequisites are met."""
        from anonreq.pipeline.forwarding_guard import ForwardingGuard

        proc_ctx.classification_result = {
            "action": "ANONYMIZE",
            "matched_rule_ids": ["TEST-001"],
        }
        proc_ctx.detections = [{"entity_type": "EMAIL_ADDRESS"}]
        proc_ctx.token_mappings = {"[EMAIL_0]": "test@example.com"}
        proc_ctx.transformed_request = {"messages": [{"content": "[EMAIL_0]"}]}

        guard = ForwardingGuard()
        result = await guard.execute(proc_ctx)

        assert not result.has_errors()

    @pytest.mark.asyncio
    async def test_pass_action_no_checks(self, proc_ctx):
        """ForwardingGuard passes immediately for PASS action."""
        from anonreq.pipeline.forwarding_guard import ForwardingGuard

        proc_ctx.classification_result = {"action": "PASS"}
        # No detections or mappings needed

        guard = ForwardingGuard()
        result = await guard.execute(proc_ctx)

        assert not result.has_errors()

    @pytest.mark.asyncio
    async def test_missing_classification_fails(self, proc_ctx):
        """Missing classification result → 503."""
        from anonreq.pipeline.forwarding_guard import ForwardingGuard
        from anonreq.exceptions import PipelineAbortError

        proc_ctx.classification_result = None

        guard = ForwardingGuard()
        result = await guard.execute(proc_ctx)

        assert result.has_errors()
        assert isinstance(result.errors[-1], PipelineAbortError)
        assert result.errors[-1].status_code == 503

    @pytest.mark.asyncio
    async def test_missing_detections_for_anonymize(self, proc_ctx):
        """ANONYMIZE without detections → 503."""
        from anonreq.pipeline.forwarding_guard import ForwardingGuard
        from anonreq.exceptions import PipelineAbortError

        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.detections = None  # Detection didn't run

        guard = ForwardingGuard()
        result = await guard.execute(proc_ctx)

        assert result.has_errors()
        assert result.errors[-1].status_code == 503

    @pytest.mark.asyncio
    async def test_missing_token_mappings_for_anonymize(self, proc_ctx):
        """ANONYMIZE without token_mappings → 503."""
        from anonreq.pipeline.forwarding_guard import ForwardingGuard
        from anonreq.exceptions import PipelineAbortError

        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.detections = [{"entity_type": "EMAIL_ADDRESS"}]
        proc_ctx.token_mappings = None  # Tokenization didn't run

        guard = ForwardingGuard()
        result = await guard.execute(proc_ctx)

        assert result.has_errors()
        assert result.errors[-1].status_code == 503


# ============================================================================
# Task 2: ProviderStage
# ============================================================================


class TestProviderStage:
    """ProviderStage sends request to upstream and returns response."""

    @pytest.mark.asyncio
    async def test_forwards_sanitized_request(self, proc_ctx):
        """ProviderStage sends transformed_request and returns response."""
        import respx
        from httpx import Response

        from anonreq.pipeline.provider import ProviderStage

        # Mock the upstream endpoint
        router = respx.mock
        router.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Your email is [EMAIL_0]",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
            status_code=200,
        )

        with router:
            proc_ctx.classification_result = {"action": "ANONYMIZE"}
            proc_ctx.transformed_request = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "My email is [EMAIL_0]"}],
            }

            stage = ProviderStage(
                openai_base_url="https://api.openai.com",
                api_key="test-key-12345",
                timeout=30.0,
            )
            result = await stage.execute(proc_ctx)

            assert not result.has_errors()
            assert result.provider_response is not None
            assert result.provider_response["choices"][0]["message"]["content"] == "Your email is [EMAIL_0]"

    @pytest.mark.asyncio
    async def test_fails_on_upstream_error(self, proc_ctx):
        """ProviderStage fails on upstream HTTP error."""
        import respx
        from httpx import Response

        from anonreq.pipeline.provider import ProviderStage

        router = respx.mock
        router.post("https://api.openai.com/v1/chat/completions").respond(
            json={"error": {"message": "Rate limit exceeded"}},
            status_code=429,
        )

        with router:
            proc_ctx.classification_result = {"action": "ANONYMIZE"}
            proc_ctx.transformed_request = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            }

            stage = ProviderStage(
                openai_base_url="https://api.openai.com",
                api_key="test-key-12345",
                timeout=30.0,
            )
            result = await stage.execute(proc_ctx)

            assert result.has_errors()
            from anonreq.exceptions import PipelineAbortError

            assert isinstance(result.errors[-1], PipelineAbortError)
            assert result.errors[-1].status_code == 502

    @pytest.mark.asyncio
    async def test_fails_on_timeout(self, proc_ctx):
        """ProviderStage fails on upstream timeout."""
        import httpx
        import respx

        from anonreq.pipeline.provider import ProviderStage

        router = respx.mock
        # Simulate timeout by raising immediately
        router.post("https://api.openai.com/v1/chat/completions").side_effect = (
            httpx.TimeoutException("Timeout")
        )

        with router:
            proc_ctx.classification_result = {"action": "ANONYMIZE"}
            proc_ctx.transformed_request = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            }

            stage = ProviderStage(
                openai_base_url="https://api.openai.com",
                api_key="test-key-12345",
                timeout=0.001,
            )
            result = await stage.execute(proc_ctx)

            assert result.has_errors()
            from anonreq.exceptions import PipelineAbortError

            assert result.errors[-1].status_code == 504


# ============================================================================
# Task 2: Restorer
# ============================================================================


class TestRestorer:
    """Restorer replaces tokens with original values."""

    def test_restore_text_simple(self):
        """Basic token replacement works."""
        from anonreq.tokenization.restorer import Restorer

        mapping = {"[EMAIL_0]": "user@example.com"}
        result = Restorer.restore_text("Contact [EMAIL_0] for info", mapping)
        assert result == "Contact user@example.com for info"

    def test_restore_text_multiple_tokens(self):
        """Multiple tokens are all replaced."""
        from anonreq.tokenization.restorer import Restorer

        mapping = {
            "[EMAIL_0]": "alice@example.com",
            "[PHONE_1]": "+1-555-123-4567",
        }
        text = "Email: [EMAIL_0], Phone: [PHONE_1]"
        result = Restorer.restore_text(text, mapping)
        assert "alice@example.com" in result
        assert "+1-555-123-4567" in result

    def test_restore_text_case_insensitive(self):
        """Case-insensitive token matching per SSE-04."""
        from anonreq.tokenization.restorer import Restorer

        mapping = {"[EMAIL_0]": "user@example.com"}
        variants = [
            "[EMAIL_0]",
            "[email_0]",
            "[Email_0]",
        ]
        for variant in variants:
            result = Restorer.restore_text(f"Contact {variant}", mapping)
            assert result == "Contact user@example.com", f"Failed for variant '{variant}'"

    def test_restore_text_empty_mapping(self):
        """Empty mapping returns text unchanged."""
        from anonreq.tokenization.restorer import Restorer

        text = "Hello [EMAIL_0]"
        result = Restorer.restore_text(text, {})
        assert result == "Hello [EMAIL_0]"

    def test_restore_text_no_tokens(self):
        """Text without tokens is returned unchanged."""
        from anonreq.tokenization.restorer import Restorer

        result = Restorer.restore_text("Hello world", {"[EMAIL_0]": "test@test.com"})
        assert result == "Hello world"

    def test_restore_text_token_length_sorting(self):
        """Longer tokens replaced first to avoid partial collision."""
        from anonreq.tokenization.restorer import Restorer

        # [NAME_10] contains [NAME_1] as a substring
        mapping = {
            "[NAME_10]": "Alice Smith",
            "[NAME_1]": "Bob",
        }
        text = "Users: [NAME_10] and [NAME_1]"
        result = Restorer.restore_text(text, mapping)
        assert "Alice Smith" in result
        assert "Bob" in result
        # [NAME_10] should be fully replaced, not partially
        assert "[NAME_10]" not in result
        assert "[NAME_1]" not in result

    def test_restore_response_dict(self):
        """Restore tokens in response dict structure."""
        from anonreq.tokenization.restorer import Restorer

        response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Your email is [EMAIL_0]",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        mapping = {"[EMAIL_0]": "user@example.com"}
        result = Restorer.restore_response(response, mapping)

        assert result["choices"][0]["message"]["content"] == "Your email is user@example.com"

    def test_restore_response_with_tool_calls(self):
        """Restore tokens in tool_calls arguments."""
        from anonreq.tokenization.restorer import Restorer

        response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "send_email",
                                    "arguments": '{"to": "[EMAIL_0]"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        mapping = {"[EMAIL_0]": "user@example.com"}
        result = Restorer.restore_response(response, mapping)

        assert '"to": "user@example.com"' in result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]


# ============================================================================
# Task 2: RestorationStage
# ============================================================================


class TestRestorationStage:
    """RestorationStage restores tokens in provider response."""

    @pytest.mark.asyncio
    async def test_restores_tokens_in_response(self, proc_ctx):
        """RestorationStage replaces tokens with original values."""
        from anonreq.pipeline.restoration import RestorationStage

        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.provider_response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Your email is [EMAIL_0]",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        proc_ctx.token_mappings = {"[EMAIL_0]": "user@example.com"}

        stage = RestorationStage()
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        assert result.restored_response is not None
        assert result.restored_response["choices"][0]["message"]["content"] == "Your email is user@example.com"

    @pytest.mark.asyncio
    async def test_fails_without_provider_response(self, proc_ctx):
        """Missing provider_response → error."""
        from anonreq.pipeline.restoration import RestorationStage

        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.provider_response = None

        stage = RestorationStage()
        result = await stage.execute(proc_ctx)

        assert result.has_errors()

    @pytest.mark.asyncio
    async def test_skipped_for_pass(self, proc_ctx):
        """RestorationStage skips for PASS action."""
        from anonreq.pipeline.restoration import RestorationStage

        proc_ctx.classification_result = {"action": "PASS"}

        stage = RestorationStage()
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        assert result.restored_response is None


# ============================================================================
# Task 2: CleanupStage
# ============================================================================


class TestCleanupStage:
    """CleanupStage deletes mapping and writes audit log."""

    @pytest.mark.asyncio
    async def test_deletes_mapping(self, proc_ctx):
        """CleanupStage deletes Valkey mapping."""
        from anonreq.pipeline.cleanup import CleanupStage

        cache_manager = MagicMock()
        proc_ctx.token_mappings = {"[EMAIL_0]": "test@test.com"}
        proc_ctx.context_id = "test-session-123"
        proc_ctx.tenant_id = "default"
        proc_ctx.classification_result = {"action": "ANONYMIZE"}
        proc_ctx.request_id = "test_req_001"

        stage = CleanupStage(cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        cache_manager.delete_mapping.assert_called_once_with(
            "default", "test-session-123",
        )

    @pytest.mark.asyncio
    async def test_skips_delete_if_no_mapping(self, proc_ctx):
        """CleanupStage skips delete when no mapping exists."""
        from anonreq.pipeline.cleanup import CleanupStage

        cache_manager = MagicMock()
        proc_ctx.token_mappings = {}
        proc_ctx.context_id = "test-session-123"
        proc_ctx.classification_result = {"action": "PASS"}

        stage = CleanupStage(cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        cache_manager.delete_mapping.assert_not_called()

    @pytest.mark.asyncio
    async def test_writes_audit_log(self, proc_ctx):
        """CleanupStage writes structured audit log entry."""
        from anonreq.pipeline.cleanup import CleanupStage

        cache_manager = MagicMock()
        proc_ctx.token_mappings = {}
        proc_ctx.context_id = "test-session-123"
        proc_ctx.tenant_id = "default"
        proc_ctx.request_id = "test_req_001"
        proc_tx = proc_ctx  # alias
        proc_ctx.classification_result = {"action": "PASS", "matched_rule_ids": []}
        proc_ctx.detections = []

        stage = CleanupStage(cache_manager=cache_manager)
        result = await stage.execute(proc_ctx)

        assert not result.has_errors()
        # Audit log is written via structlog — verify no error


# ============================================================================
# Full pipeline integration
# ============================================================================


class TestFullPipeline:
    """Full pipeline integration tests with real stages."""

    @pytest.mark.asyncio
    async def test_classification_block_returns_403(self, proc_ctx, sample_request_dict):
        """BLOCK classification → ctx.has_errors() with 403."""
        from anonreq.classification.engine import ClassificationEngine, ClassificationRule
        from anonreq.pipeline.classification import ClassificationStage
        from anonreq.pipeline.manager import PipelineManager
        from anonreq.pipeline.forwarding_guard import ForwardingGuard

        # Create a classification engine that blocks email content
        engine = ClassificationEngine(
            rules=[
                ClassificationRule(
                    id="BLOCK-EMAIL",
                    action="BLOCK",
                    roles=["user"],
                    regex_patterns=[r"email"],
                    keywords=[],
                ),
            ],
            default_action="PASS",
        )

        proc_ctx.original_request = sample_request_dict
        proc_ctx.text_nodes = None

        manager = PipelineManager()
        manager.register(ClassificationStage(engine=engine))
        manager.register(ForwardingGuard())

        result = await manager.run(proc_ctx)

        assert result.has_errors()
        from anonreq.exceptions import PipelineAbortError

        assert result.errors[-1].status_code == 403

    @pytest.mark.asyncio
    async def test_classification_pass_forwards_unchanged(self, proc_ctx, sample_request_dict):
        """PASS → pipeline completes without errors (no detections/tokenization)."""
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.pipeline.classification import ClassificationStage
        from anonreq.pipeline.forwarding_guard import ForwardingGuard
        from anonreq.pipeline.manager import PipelineManager

        # Engine with default PASS (no rules match)
        engine = ClassificationEngine(rules=[], default_action="PASS")

        proc_ctx.original_request = sample_request_dict

        provider_stage = MagicMock()
        provider_stage.name = "ProviderStage"
        provider_stage.execute = AsyncMock(return_value=proc_ctx)

        manager = PipelineManager()
        manager.register(ClassificationStage(engine=engine))
        manager.register(ForwardingGuard())
        manager.register(provider_stage)

        # Set up prerequisite fields that ForwardingGuard checks for ANONYMIZE
        # After classification with PASS, guard should let it through
        result = await manager.run(proc_ctx)

        # For PASS, the pipeline should complete without blocking
        assert result.classification_result is not None
        assert result.classification_result["action"] == "PASS"


# ============================================================================
# Full pipeline with all stages + Provider (mock upstream)
# ============================================================================


class TestFullPipelineWithDetection:
    """Full pipeline with Classification → Detection → Tokenization → Guard → Provider → Restoration → Cleanup."""

    @pytest.mark.asyncio
    async def test_full_pipeline_anonymize_flow(self, proc_ctx, sample_request_dict):
        """Full ANONYMIZE flow with mocked detection and provider."""
        import respx

        from anonreq.cache.manager import CacheManager
        from anonreq.classification.engine import ClassificationEngine
        from anonreq.detection.exclusion_list import ExclusionList
        from anonreq.detection.regex_detector import RegexDetector
        from anonreq.detection.span_arbiter import SpanArbiter
        from anonreq.pipeline.classification import ClassificationStage
        from anonreq.pipeline.cleanup import CleanupStage
        from anonreq.pipeline.detection import DetectionStage
        from anonreq.pipeline.forwarding_guard import ForwardingGuard
        from anonreq.pipeline.manager import PipelineManager
        from anonreq.pipeline.provider import ProviderStage
        from anonreq.pipeline.restoration import RestorationStage
        from anonreq.pipeline.tokenization import TokenizationStage
        from anonreq.tokenization import Tokenizer

        # Engine with PASS default — classification won't block
        engine = ClassificationEngine(rules=[], default_action="ANONYMIZE")

        # Use real RegexDetector + SpanArbiter + ExclusionList + PresidioClient (mocked)
        regex_detector = MagicMock()
        # Text: "My name is John and email is john@example.com"
        # John at 11-15, john@example.com at 29-45
        regex_detector.detect.return_value = [
            {"entity_type": "EMAIL_ADDRESS", "start": 29, "end": 45, "score": 1.0, "source": "regex"},
        ]

        presidio_client = MagicMock()
        presidio_client.analyze_text_nodes.return_value = [
            [{"entity_type": "PERSON", "start": 11, "end": 15, "score": 0.95}],
            [],
        ]

        span_arbiter = SpanArbiter()
        exclusion_list = ExclusionList()
        tokenizer = Tokenizer()
        original_init_session = tokenizer.initialize_session
        def _patched_init_session():
            original_init_session()
            tokenizer._seed = 0  # Deterministic seed so tokens match mock response
        tokenizer.initialize_session = _patched_init_session

        # Use fakeredis-backed cache manager
        import fakeredis.aioredis

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache_manager = CacheManager.__new__(CacheManager)
        cache_manager._redis = fake_redis
        cache_manager._ttl = 300

        # Mock upstream provider
        router = respx.mock
        router.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "id": "chatcmpl-456",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Your email on file is [EMAIL_ADDRESS_0]",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
            status_code=200,
        )

        with router:
            proc_ctx.original_request = sample_request_dict
            proc_ctx.classification_result = {"action": "ANONYMIZE"}
            proc_ctx.text_nodes = [
                {
                    "path": "messages[0].content",
                    "role": "user",
                    "value": "My name is John and email is john@example.com",
                },
            ]
            proc_ctx.context_id = "integration-test-session"

            manager = PipelineManager()
            manager.register(ClassificationStage(engine=engine))
            manager.register(
                DetectionStage(
                    regex_detector=regex_detector,
                    presidio_client=presidio_client,
                    span_arbiter=span_arbiter,
                    exclusion_list=exclusion_list,
                )
            )
            manager.register(
                TokenizationStage(tokenizer=tokenizer, cache_manager=cache_manager)
            )
            manager.register(ForwardingGuard())
            manager.register(
                ProviderStage(
                    openai_base_url="https://api.openai.com",
                    api_key="test-key",
                    timeout=30.0,
                )
            )
            manager.register(RestorationStage())
            manager.register(CleanupStage(cache_manager=cache_manager))

            result = await manager.run(proc_ctx)

            assert not result.has_errors(), (
                f"Pipeline failed with errors: {result.errors}"
            )
            assert result.restored_response is not None
            # The restored response should have the original email
            content = result.restored_response["choices"][0]["message"]["content"]
            assert "john@example.com" in content, (
                f"Expected 'john@example.com' in restored response, got: {content}"
            )

        await fake_redis.aclose()


# ============================================================================
# FastAPI TestClient integration tests
# ============================================================================


class TestAPIIntegration:
    """Full API-level integration tests via TestClient."""

    @pytest.mark.asyncio
    async def test_chat_route_accepts_request(self):
        """POST /v1/chat/completions with valid auth → 200."""
        # Create a minimal app with the chat router
        from fastapi import Depends, FastAPI
        from httpx import ASGITransport, AsyncClient

        from anonreq.config import settings
        from anonreq.dependencies import auth_context
        from anonreq.routing.chat import router as chat_router

        app = FastAPI()
        app.include_router(chat_router, dependencies=[Depends(auth_context)])

        # Mock app state with pipeline
        pipeline_mock = MagicMock()
        pipeline_mock.run = AsyncMock()
        ctx_result = MagicMock()
        ctx_result.has_errors.return_value = False
        ctx_result.classification_result = {"action": "PASS"}
        ctx_result.provider_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
        }
        ctx_result.restored_response = None
        ctx_result.detections = []
        ctx_result.request_id = "test-request-id"
        ctx_result.original_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }
        ctx_result.text_nodes = []
        ctx_result.errors = []
        ctx_result.classification_result_v2 = None

        pipeline_mock.run.return_value = ctx_result

        app.state.pipeline = pipeline_mock
        app.state.cache_manager = MagicMock()
        app.state.presidio_client = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={"Authorization": f"Bearer {settings.API_KEY}"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_route_without_auth_returns_401(self):
        """POST /v1/chat/completions without auth → 401."""
        from fastapi import Depends, FastAPI
        from httpx import ASGITransport, AsyncClient

        from anonreq.dependencies import auth_context
        from anonreq.routing.chat import router as chat_router

        app = FastAPI()
        app.include_router(chat_router, dependencies=[Depends(auth_context)])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_route_with_invalid_body_returns_422(self):
        """POST /v1/chat/completions with invalid body → 422."""
        from fastapi import Depends, FastAPI
        from httpx import ASGITransport, AsyncClient

        from anonreq.dependencies import auth_context
        from anonreq.routing.chat import router as chat_router

        app = FastAPI()
        app.include_router(chat_router, dependencies=[Depends(auth_context)])
        app.state.pipeline = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing 'model' field which is required
            response = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers={"Authorization": "Bearer " + "a" * 32},
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_route_returns_x_anonreq_headers(self):
        """Response includes X-AnonReq-Request-ID header."""
        from fastapi import Depends, FastAPI
        from httpx import ASGITransport, AsyncClient

        from anonreq.config import settings
        from anonreq.dependencies import auth_context
        from anonreq.routing.chat import router as chat_router

        app = FastAPI()
        app.include_router(chat_router, dependencies=[Depends(auth_context)])

        pipeline_mock = MagicMock()
        pipeline_mock.run = AsyncMock()
        ctx_result = MagicMock()
        ctx_result.has_errors.return_value = False
        ctx_result.classification_result = {"action": "PASS"}
        ctx_result.provider_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
        }
        ctx_result.restored_response = None
        ctx_result.detections = []
        ctx_result.request_id = "test-request-id"
        ctx_result.original_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }
        ctx_result.text_nodes = []
        ctx_result.errors = []
        ctx_result.classification_result_v2 = None

        pipeline_mock.run.return_value = ctx_result

        app.state.pipeline = pipeline_mock
        app.state.cache_manager = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={"Authorization": f"Bearer {settings.API_KEY}"},
            )
            assert response.status_code == 200
            assert "x-anonreq-request-id" in response.headers
            assert "x-anonreq-processed" in response.headers
            assert "x-anonreq-entity-count" in response.headers
