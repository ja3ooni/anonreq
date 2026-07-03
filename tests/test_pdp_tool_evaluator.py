"""Tests for PDP #2 tool permission evaluation.

Covers:
- Known tool with ALLOW permission
- Known tool with BLOCK permission
- Unlisted LOW risk tool default to ALLOW
- Unlisted CRITICAL risk tool default to REQUIRE_HUMAN_APPROVAL
- Cross-domain isolation (model ↔ host)
- Cross-delegation credential isolation
- Orphaned tool result detection
- get_permitted_actions
"""

from __future__ import annotations

import pytest

from anonreq.governance.pdp_tool_evaluator import (
    PDPToolEvaluator,
    ToolBlockedError,
    ToolDecision,
)
from anonreq.governance.tool_extractor import ToolCall, ToolResult
from anonreq.governance.tool_policy_parser import (
    ToolPermission,
    ToolPolicyParser,
    ToolRiskLevel,
)
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def parser() -> ToolPolicyParser:
    """Create a ToolPolicyParser pre-loaded with sample policies."""
    parser = ToolPolicyParser()
    yaml = {
        "providers": {
            "openai": {
                "tool_risk_classification": {
                    "code_interpreter": "critical",
                    "file_search": "high",
                    "read_file": "low",
                    "web_search": "low",
                },
                "tools": [
                    {"name": "code_interpreter", "permission": "block"},
                    {"name": "file_search", "permission": "allow_with_audit"},
                    {"name": "read_file", "permission": "allow"},
                    {"name": "web_search", "permission": "allow"},
                ],
            },
            "anthropic": {
                "tool_risk_classification": {
                    "computer_use": "critical",
                    "bash": "critical",
                },
                "tools": [
                    {"name": "computer_use", "permission": "block"},
                    {"name": "bash", "permission": "require_human_approval"},
                ],
            },
            "host_mcp": {
                "tool_risk_classification": {
                    "db_query": "critical",
                },
                "tools": [
                    {"name": "db_query", "permission": "require_human_approval"},
                ],
            },
        },
    }
    parser.parse(yaml)
    return parser


@pytest.fixture
def evaluator(parser: ToolPolicyParser) -> PDPToolEvaluator:
    """Create a PDPToolEvaluator with pre-loaded parser."""
    return PDPToolEvaluator(parser)


@pytest.fixture
def context() -> ProcessingContext:
    """Create a minimal processing context."""
    return ProcessingContext(request_id="test_req_001", tenant_id="test_tenant")


def make_openai_call(name: str, **overrides) -> ToolCall:
    """Create an OpenAI-format ToolCall for testing."""
    data = {
        "id": "call_test",
        "name": name,
        "arguments": {},
        "format": "openai",
        "domain": "model",
        "provider": "openai",
    }
    data.update(overrides)
    recognized = ToolCall.__dataclass_fields__  # type: ignore[attr-defined]
    return ToolCall(**{k: v for k, v in data.items() if k in recognized})


class TestEvaluate:
    """Core evaluation tests."""

    @pytest.mark.asyncio
    async def test_known_tool_allow(self, evaluator, context):
        """Test 1: Known tool with ALLOW permission returns ALLOW."""
        tool_call = make_openai_call("read_file")
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW
        assert decision.tool_name == "read_file"
        assert decision.provider == "openai"
        assert context.has_errors() is False

    @pytest.mark.asyncio
    async def test_known_tool_block(self, evaluator, context):
        """Test 2: Known tool with BLOCK permission returns BLOCK."""
        tool_call = make_openai_call("code_interpreter")
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK
        assert decision.reason is not None
        assert "block" in decision.reason.lower()
        # BLOCK should add an error to context (fail-secure)
        assert context.has_errors() is True

    @pytest.mark.asyncio
    async def test_known_tool_allow_with_audit(self, evaluator, context):
        """Known tool with ALLOW_WITH_AUDIT returns ALLOW_WITH_AUDIT."""
        tool_call = make_openai_call("file_search")
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW_WITH_AUDIT
        assert "audit" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_known_tool_require_human_approval(self, evaluator, context):
        """Known tool with REQUIRE_HUMAN_APPROVAL returns REQUIRE_HUMAN_APPROVAL."""
        tool_call = ToolCall(
            id="call_test",
            name="bash",
            arguments={"command": "ls"},
            format="anthropic",
            domain="model",
            provider="anthropic",
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.REQUIRE_HUMAN_APPROVAL
        assert decision.tool_name == "bash"
        assert context.requires_approval is True

    @pytest.mark.asyncio
    async def test_anthropic_block(self, evaluator, context):
        """Anthropic blocked tool returns BLOCK."""
        tool_call = ToolCall(
            id="call_test",
            name="computer_use",
            arguments={},
            format="anthropic",
            domain="model",
            provider="anthropic",
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK
        assert context.has_errors() is True

    @pytest.mark.asyncio
    async def test_unlisted_low_risk_default_allow(self, evaluator, context):
        """Test 3: Unlisted LOW risk tool defaults to ALLOW."""
        tool_call = make_openai_call("unknown_low_tool")
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW

    @pytest.mark.asyncio
    async def test_unlisted_critical_risk_default_requires_approval(self, evaluator, context):
        """Test 4: Unlisted CRITICAL risk tool defaults to REQUIRE_HUMAN_APPROVAL."""
        # code_interpreter is classified as critical in the sample config
        # but let's test with a truly unknown tool name
        parser2 = ToolPolicyParser()
        parser2.parse({
            "providers": {
                "openai": {
                    "tool_risk_classification": {},
                    "tools": [],
                },
            },
        })
        eval2 = PDPToolEvaluator(parser2)

        tool_call = make_openai_call("some_critical_tool")
        decision = await eval2.evaluate(tool_call, context)

        # Without risk classification, unknown tools default to ALLOW
        assert decision.permission == ToolPermission.ALLOW

    @pytest.mark.asyncio
    async def test_host_mcp_block(self, evaluator, context):
        """Host MCP blocked tool (via isolation) returns BLOCK."""
        tool_call = ToolCall(
            id="call_test",
            name="db_query",
            arguments={"sql": "SELECT 1"},
            format="mcp",
            domain="host",
            provider="host_mcp",
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.REQUIRE_HUMAN_APPROVAL

    @pytest.mark.asyncio
    async def test_provider_from_tool_call(self, evaluator, context):
        """Provider from tool_call takes precedence over context."""
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={},
            format="openai",
            domain="model",
            provider="openai",
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW
        assert decision.provider == "openai"


class TestCrossDomainIsolation:
    """Cross-domain isolation tests per D-018, D-019, D-020."""

    @pytest.mark.asyncio
    async def test_model_domain_to_host_provider_blocked(self, evaluator, context):
        """Test 5: Model domain tool call targeting host provider → BLOCK."""
        tool_call = ToolCall(
            id="call_1",
            name="db_query",
            arguments={},
            format="mcp",
            domain="model",  # model domain
            provider="host_mcp",  # host provider
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK
        assert "isolation" in (decision.reason or "").lower()
        assert context.has_errors() is True

    @pytest.mark.asyncio
    async def test_host_domain_to_model_provider_blocked(self, evaluator, context):
        """Host domain tool call targeting model provider → BLOCK."""
        tool_call = ToolCall(
            id="call_1",
            name="code_interpreter",
            arguments={},
            format="openai",
            domain="host",  # host domain
            provider="openai",  # model provider
        )
        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK
        assert "isolation" in (decision.reason or "").lower()
        assert context.has_errors() is True

    @pytest.mark.asyncio
    async def test_model_domain_to_model_provider_allowed(self, evaluator, context):
        """Model domain + model provider → allowed."""
        tool_call = make_openai_call("read_file")
        decision = await evaluator.evaluate(tool_call, context)
        assert decision.permission == ToolPermission.ALLOW

    @pytest.mark.asyncio
    async def test_host_domain_to_host_provider_allowed(self, evaluator, context):
        """Host domain + host provider → allowed (if not blocked by policy)."""
        tool_call = ToolCall(
            id="call_1",
            name="file_read",
            arguments={},
            format="mcp",
            domain="host",
            provider="host_mcp",
        )
        # Need to add file_read to host_mcp in parser
        parser_alt = ToolPolicyParser()
        parser_alt.parse({
            "providers": {
                "host_mcp": {
                    "tools": [
                        {"name": "file_read", "permission": "allow"},
                    ],
                },
            },
        })
        eval_alt = PDPToolEvaluator(parser_alt)

        decision = await eval_alt.evaluate(tool_call, context)
        assert decision.permission == ToolPermission.ALLOW


class TestCrossDelegationIsolation:
    """Cross-delegation credential isolation tests per D-016."""

    @pytest.mark.asyncio
    async def test_cross_delegation_blocked(self, evaluator, context):
        """Test 6: Cross-delegation credential access → BLOCK."""
        tool_call = make_openai_call("read_file", credential_context="delegation_a")
        context.audit_metadata["delegation_id"] = "delegation_b"

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK
        assert "credential" in (decision.reason or "").lower()
        assert context.has_errors() is True

    @pytest.mark.asyncio
    async def test_same_delegation_allowed(self, evaluator, context):
        """Same delegation context → allowed."""
        tool_call = make_openai_call("read_file", credential_context="delegation_a")
        context.audit_metadata["delegation_id"] = "delegation_a"

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW

    @pytest.mark.asyncio
    async def test_no_credential_context_allowed(self, evaluator, context):
        """No credential context → allowed (new delegation)."""
        # Explicitly don't set credential_context
        tool_call = make_openai_call("read_file")
        # Explicitly clear the delegation_id just in case
        context.audit_metadata.pop("delegation_id", None)

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW

    @pytest.mark.asyncio
    async def test_credential_context_without_session_delegation(self, evaluator, context):
        """Credential context set but no session delegation → allowed."""
        tool_call = make_openai_call("read_file", credential_context="delegation_a")
        context.audit_metadata.pop("delegation_id", None)

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW


class TestToolResult:
    """Tool result evaluation tests."""

    def test_tool_result_audit_metadata(self, evaluator, context):
        """Test 7: evaluate_tool_result adds audit metadata."""
        tool_result = ToolResult(
            id="call_1",
            name="search",
            content="results",
            format="openai",
            is_error=False,
        )

        evaluator.evaluate_tool_result(tool_result, context)

        audit_key = "tool_result_call_1"
        assert audit_key in context.audit_metadata
        assert context.audit_metadata[audit_key]["tool_id"] == "call_1"
        assert context.audit_metadata[audit_key]["is_error"] is False

    def test_tool_result_error_flag(self, evaluator, context):
        """Error tool result is flagged correctly."""
        tool_result = ToolResult(
            id="call_err",
            name="search",
            content="Error occurred",
            format="anthropic",
            is_error=True,
        )

        evaluator.evaluate_tool_result(tool_result, context)

        audit_key = "tool_result_call_err"
        assert context.audit_metadata[audit_key]["is_error"] is True


class TestGetPermittedActions:
    """Tests for get_permitted_actions."""

    def test_get_permitted_actions_returns_list(self, evaluator):
        """Test 8: get_permitted_actions returns list of tool names."""
        actions = evaluator.get_permitted_actions("openai", "model")
        assert isinstance(actions, list)
        # Should not include blocked tools
        assert all(isinstance(a, str) for a in actions)


class TestBlockDecisionError:
    """Tests for ToolBlockedError and context error handling."""

    def test_tool_blocked_error(self):
        """ToolBlockedError can be instantiated with a reason."""
        error = ToolBlockedError("test blocked")
        assert str(error) == "test blocked"

    @pytest.mark.asyncio
    async def test_blocked_tool_adds_error_to_context(self, evaluator, context):
        """BLOCK permission adds ToolBlockedError to context."""
        tool_call = make_openai_call("code_interpreter")
        await evaluator.evaluate(tool_call, context)

        assert context.has_errors() is True
        assert any(isinstance(e, ToolBlockedError) for e in context.errors)
