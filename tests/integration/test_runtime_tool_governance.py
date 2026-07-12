"""Integration tests for tool governance pipeline stage registered in the runtime pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.governance.pdp_tool_evaluator import ToolBlockedError
from anonreq.governance.tool_policy_parser import ToolPermission
from anonreq.models.processing_context import ProcessingContext


class TestRuntimeToolGovernance:
    """Tests that the runtime pipeline correctly evaluates tool calls."""

    @pytest.mark.asyncio
    async def test_tool_governance_stage_evaluates_openai_tool_calls(self):
        """ToolGovernanceStage evaluates OpenAI tool calls from ctx.original_request."""
        from anonreq.pipeline.tool_governance import ToolGovernanceStage

        tool_evaluator = AsyncMock()
        tool_evaluator.evaluate.return_value = MagicMock(
            permission=ToolPermission.ALLOW,
            tool_name="test_tool",
            provider="openai",
        )

        app_state = MagicMock()
        app_state.tool_evaluator = tool_evaluator

        stage = ToolGovernanceStage(app_state=app_state)
        ctx = ProcessingContext(request_id="test_001", tenant_id="default")
        ctx.original_request = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "test_tool",
                                "arguments": '{"key": "value"}',
                            },
                        },
                    ],
                },
            ],
        }

        ctx = await stage.execute(ctx)

        assert not ctx.has_errors()
        tool_evaluator.evaluate.assert_awaited()

    @pytest.mark.asyncio
    async def test_block_decisions_call_fail_secure(self):
        """BLOCK decisions call ctx.fail_secure() and prevent provider forwarding."""
        from anonreq.pipeline.tool_governance import ToolGovernanceStage

        tool_evaluator = AsyncMock()
        tool_evaluator.evaluate.side_effect = ToolBlockedError("Tool 'malicious_tool' is blocked by policy")  # noqa: E501

        app_state = MagicMock()
        app_state.tool_evaluator = tool_evaluator

        stage = ToolGovernanceStage(app_state=app_state)
        ctx = ProcessingContext(request_id="test_002", tenant_id="default")
        ctx.original_request = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_456",
                            "type": "function",
                            "function": {
                                "name": "malicious_tool",
                                "arguments": '{"cmd": "rm -rf /"}',
                            },
                        },
                    ],
                },
            ],
        }

        ctx = await stage.execute(ctx)

        assert ctx.has_errors()
        assert isinstance(ctx.errors[-1], ToolBlockedError)

    @pytest.mark.asyncio
    async def test_malformed_arguments_fail_closed(self):
        """Malformed tool arguments fail closed rather than bypassing governance."""
        from anonreq.pipeline.tool_governance import ToolGovernanceStage

        tool_evaluator = AsyncMock()

        app_state = MagicMock()
        app_state.tool_evaluator = tool_evaluator

        stage = ToolGovernanceStage(app_state=app_state)
        ctx = ProcessingContext(request_id="test_003", tenant_id="default")
        ctx.original_request = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_789",
                            "type": "function",
                            "function": {
                                "name": "some_tool",
                                "arguments": "not valid json{{{",
                            },
                        },
                    ],
                },
            ],
        }

        ctx = await stage.execute(ctx)

        assert ctx.has_errors()
        assert isinstance(ctx.errors[-1], ToolBlockedError)
        assert "Failed to extract tool calls" in str(ctx.errors[-1])
