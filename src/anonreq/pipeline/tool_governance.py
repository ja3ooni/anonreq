"""Tool governance pipeline stage for agent/tool call enforcement."""
from __future__ import annotations

from typing import Any

from anonreq.governance.pdp_tool_evaluator import ToolBlockedError
from anonreq.governance.tool_extractor import ToolExtractor
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage


class ToolGovernanceStage(PipelineStage):
    """Evaluates tool calls in the request against permission policies.

    Extracts tool calls from OpenAI/Anthropic/MCP formats using ToolExtractor,
    evaluates them with PDPToolEvaluator, and blocks or suspends as needed.
    """

    def __init__(
        self,
        app_state: Any | None = None,
    ) -> None:
        super().__init__("ToolGovernanceStage")
        self._app_state = app_state
        self._extractor = ToolExtractor()

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        if self._app_state is None:
            return ctx

        tool_evaluator = getattr(self._app_state, "tool_evaluator", None)
        if tool_evaluator is None:
            return ctx

        request_body = ctx.original_request
        if not isinstance(request_body, dict):
            return ctx

        headers = {}
        tool_format = self._extractor.detect_format(request_body, headers)
        if tool_format is None:
            return ctx

        messages = request_body.get("messages", [])
        if not isinstance(messages, list):
            return ctx

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            try:
                calls = self._extractor.extract_calls(msg, tool_format)
            except (KeyError, TypeError, ValueError) as exc:
                ctx.fail_secure(ToolBlockedError(f"Failed to extract tool calls: {type(exc).__name__}: {exc}"))
                return ctx
            except Exception as exc:
                ctx.fail_secure(ToolBlockedError(f"Failed to extract tool calls: {type(exc).__name__}"))
                return ctx

            for call in calls:
                try:
                    await tool_evaluator.evaluate(call, ctx)
                except (KeyError, TypeError, ValueError) as exc:
                    ctx.fail_secure(ToolBlockedError(f"Tool evaluation failed for {call.name}: {type(exc).__name__}: {exc}"))
                    return ctx
                except Exception as exc:
                    ctx.fail_secure(ToolBlockedError(f"Tool evaluation failed for {call.name}: {type(exc).__name__}"))
                    return ctx

                if ctx.has_errors():
                    return ctx

        return ctx
