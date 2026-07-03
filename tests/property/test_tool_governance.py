"""Property-based tests for tool governance invariants (Plan 18-03).

Covers (must_haves):
1. Permission determinism — same tool+provider+domain → same permission
2. Format-switching bypass resistance — same tool via different format
   (openai/anthropic/mcp) yields same permission for same provider
3. Cross-domain isolation — model→host and host→model always BLOCK
4. Credential isolation — mismatched delegation always BLOCK
5. No raw values in audit events — never contains PII/token/raw args
6. Low-risk unlisted → default ALLOW

Uses Hypothesis ``@given`` strategies and the existing PDPToolEvaluator,
ToolPermission, ToolRiskLevel, ToolCall, and ProcessingContext fixtures.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from hypothesis import HealthCheck, given, assume, settings
from hypothesis import strategies as st

from anonreq.governance.audit import (
    FORBIDDEN_AUDIT_KEYS,
    ToolAuditEvent,
    ToolAuditEventType,
    emit_tool_audit_event,
    tool_audit_event_to_dict,
)
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


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def parser() -> ToolPolicyParser:
    """Pre-loaded policy parser used across all property tests.

    Loaded once per module because the policy YAML is static and parsing
    is deterministic (pure function).
    """
    parser = ToolPolicyParser()
    parser.parse(_POLICY_YAML)
    return parser


@pytest.fixture(scope="session")
def evaluator(parser: ToolPolicyParser) -> PDPToolEvaluator:
    """Return a PDPToolEvaluator with standard strict settings.

    Session-scoped because PDPToolEvaluator is effectively read-only
    after construction (no mutable state between evaluate() calls).
    """
    return PDPToolEvaluator(parser)


# ── Static policy data ───────────────────────────────────────────────────────


_POLICY_YAML: dict[str, Any] = {
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
        "gemini": {
            "tool_risk_classification": {},
            "tools": [],
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

# The set of known tool names in _POLICY_YAML
_KNOWN_TOOLS: tuple[str, ...] = (
    "code_interpreter",
    "file_search",
    "read_file",
    "web_search",
    "computer_use",
    "bash",
    "db_query",
)

# Providers
_PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "gemini", "host_mcp")

# Domains
_DOMAINS: tuple[str, ...] = ("model", "host")

# Formats
_FORMATS: tuple[str, ...] = ("openai", "anthropic", "mcp")

# Permissions (all 4)
_PERMISSIONS: tuple[str, ...] = tuple(p.value for p in ToolPermission)

# Risk levels (all 4)
_RISK_LEVELS: tuple[str, ...] = tuple(r.value for r in ToolRiskLevel)


# ── Hypothesis strategies ────────────────────────────────────────────────────


tool_name_st = st.sampled_from(_KNOWN_TOOLS)
provider_st = st.sampled_from(_PROVIDERS)
domain_st = st.sampled_from(_DOMAINS)
format_st = st.sampled_from(_FORMATS)
permission_st = st.sampled_from(_PERMISSIONS)
risk_level_st = st.sampled_from(_RISK_LEVELS)

# Strategy for delegation contexts (None = no credential context)
delegation_st = st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))

# Strategy for unknown tool names (to test default behaviour)
unknown_tool_name_st = st.text(min_size=5, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(
    lambda n: n not in _KNOWN_TOOLS and not n.startswith("test_")
)


# ── Helper ───────────────────────────────────────────────────────────────────


def _make_tool_call(
    name: str,
    format: str = "openai",
    domain: str = "model",
    provider: str = "openai",
    credential_context: str | None = None,
) -> ToolCall:
    """Create a ToolCall with default arguments."""
    return ToolCall(
        id="pcall_01",
        name=name,
        arguments={},
        format=format,
        domain=domain,
        provider=provider,
        credential_context=credential_context,
    )


def _make_context(delegation_id: str | None = None) -> ProcessingContext:
    """Create a ProcessingContext optionally carrying a delegation ID."""
    ctx = ProcessingContext(request_id="prop_test_ctx", tenant_id="default")
    if delegation_id is not None:
        ctx.audit_metadata["delegation_id"] = delegation_id
    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Permission determinism
# ═══════════════════════════════════════════════════════════════════════════════


class TestPermissionDeterminism:
    """Same tool+provider+domain always yields the same permission.

    Invariant: for any fixed tool name, provider, and domain, calling
    ``evaluate()`` twice produces the same ``ToolDecision.permission``
    and ``ToolDecision.risk_level``.

    Strategy: generate tool_name, provider, domain combinations and
    evaluate each pair of calls.
    """

    @given(
        name=tool_name_st,
        provider=provider_st,
        domain=domain_st,
        ctx_delegation=delegation_st,
    )
    @pytest.mark.asyncio
    async def test_deterministic_permission(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
        domain: str,
        ctx_delegation: str | None,
    ) -> None:
        context = _make_context(delegation_id=ctx_delegation)
        tool_call = _make_tool_call(name=name, provider=provider, domain=domain)

        decision1 = await evaluator.evaluate(tool_call, context)

        # Reset context error state for the second call so it is not
        # short-circuited by has_errors().
        context2 = _make_context(delegation_id=ctx_delegation)
        tool_call2 = _make_tool_call(name=name, provider=provider, domain=domain)
        decision2 = await evaluator.evaluate(tool_call2, context2)

        assert decision1.permission == decision2.permission, (
            f"Non-deterministic permission for {name}@{provider}/{domain}: "
            f"{decision1.permission} vs {decision2.permission}"
        )
        assert decision1.risk_level == decision2.risk_level, (
            f"Non-deterministic risk_level for {name}@{provider}/{domain}: "
            f"{decision1.risk_level} vs {decision2.risk_level}"
        )

    @given(
        name=tool_name_st,
        provider=provider_st,
        domain=domain_st,
    )
    @pytest.mark.asyncio
    async def test_decision_data_structure(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
        domain: str,
    ) -> None:
        """Every decision has the required fields set."""
        context = _make_context()
        tool_call = _make_tool_call(name=name, provider=provider, domain=domain)

        decision = await evaluator.evaluate(tool_call, context)

        assert isinstance(decision, ToolDecision)
        assert decision.tool_name == name
        assert decision.provider == provider
        assert decision.domain == domain
        assert decision.permission in ToolPermission
        assert decision.reason is not None and len(decision.reason) > 0
        assert isinstance(decision.audit, dict)
        assert "tool" in decision.audit
        assert "provider" in decision.audit
        assert "domain" in decision.audit


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Format-switching bypass resistance
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatBypassResistance:
    """Same tool via different format yields same permission for same provider.

    Invariant: a tool call in OpenAI format and one in Anthropic format
    (with the same provider, tool name, domain) must produce the same
    permission.decision.  Changing the wire format between requests must
    not change the governance outcome.

    The MCP format always targets ``host_mcp`` provider in our setup, so
    we only compare openai ↔ anthropic for model providers.
    """

    @given(
        name=st.sampled_from(("code_interpreter", "file_search", "read_file", "web_search")),
        provider=st.sampled_from(("openai",)),
    )
    @pytest.mark.asyncio
    async def test_openai_anthropic_same_tool(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
    ) -> None:
        """Same tool via openai vs anthropic format → same permission."""
        context_a = _make_context()
        context_b = _make_context()
        call_a = _make_tool_call(name=name, format="openai", domain="model", provider=provider)
        call_b = _make_tool_call(name=name, format="anthropic", domain="model", provider=provider)

        dec_a = await evaluator.evaluate(call_a, context_a)
        dec_b = await evaluator.evaluate(call_b, context_b)

        assert dec_a.permission == dec_b.permission, (
            f"Format bypass: {name} via openai={dec_a.permission} "
            f"vs anthropic={dec_b.permission}"
        )
        assert dec_a.risk_level == dec_b.risk_level, (
            f"Risk level differs by format for {name}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Cross-domain isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestCrossDomainIsolationProperty:
    """model→host and host→model always BLOCK (D-018, D-019, D-020).

    Invariant: if tool.domain != expected_domain_for(provider) then
    the result is always BLOCK with an isolation-related reason.
    """

    @given(
        name=tool_name_st,
        tool_domain=domain_st,
    )
    @pytest.mark.asyncio
    async def test_cross_domain_always_block(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        tool_domain: str,
    ) -> None:
        """model domain → host_mcp provider → BLOCK.
        host domain → openai/anthropic/gemini → BLOCK."""
        # Determine the mismatched domain pair
        if tool_domain == "model":
            provider = "host_mcp"
        else:
            provider = "openai"

        context = _make_context()
        tool_call = _make_tool_call(
            name=name, domain=tool_domain, provider=provider,
        )

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK, (
            f"Cross-domain not blocked: domain={tool_domain}, "
            f"provider={provider}, tool={name}, got={decision.permission}"
        )
        assert "isolation" in (decision.reason or "").lower(), (
            f"Block reason missing isolation for domain={tool_domain}, "
            f"provider={provider}"
        )

    @given(
        name=tool_name_st,
    )
    @pytest.mark.asyncio
    async def test_same_domain_not_blocked(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
    ) -> None:
        """model domain + model provider → NOT BLOCK (unless tool policy blocks)."""
        context = _make_context()
        tool_call = _make_tool_call(name=name, domain="model", provider="openai")

        decision = await evaluator.evaluate(tool_call, context)

        # Could be ALLOW, ALLOW_WITH_AUDIT, REQUIRE_HUMAN_APPROVAL, or BLOCK
        # (if the tool policy says BLOCK).  It should NOT be BLOCK *due to
        # domain isolation* — i.e. the reason should not mention isolation.
        if decision.permission == ToolPermission.BLOCK:
            # Must be blocked by policy, not by isolation
            assert "isolation" not in (decision.reason or "").lower(), (
                f"Same-domain call blocked for isolation: {name}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Credential isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestCredentialIsolationProperty:
    """Mismatched delegation always BLOCK (D-016).

    Invariant: if tool_call.credential_context != delegation_id in context,
    the result is always BLOCK with a credential-related reason.
    """

    @given(
        name=tool_name_st,
        tool_ctx=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        session_ctx=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
    )
    @pytest.mark.asyncio
    async def test_cross_delegation_blocked(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        tool_ctx: str,
        session_ctx: str,
    ) -> None:
        assume(tool_ctx != session_ctx)

        context = _make_context(delegation_id=session_ctx)
        tool_call = _make_tool_call(
            name=name, credential_context=tool_ctx,
        )

        decision = await evaluator.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.BLOCK, (
            f"Cross-delegation not blocked: tool_ctx={tool_ctx}, "
            f"session_ctx={session_ctx}, tool={name}, got={decision.permission}"
        )
        assert "credential" in (decision.reason or "").lower(), (
            f"Block reason missing credential for tool_ctx={tool_ctx}, "
            f"session_ctx={session_ctx}"
        )

    @given(
        name=tool_name_st,
        ctx=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
    )
    @pytest.mark.asyncio
    async def test_same_delegation_allowed(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        ctx: str,
    ) -> None:
        """Same delegation context → allowed (unless policy blocks)."""
        context = _make_context(delegation_id=ctx)
        tool_call = _make_tool_call(name=name, credential_context=ctx)

        decision = await evaluator.evaluate(tool_call, context)

        # Should NOT be blocked due to credential isolation
        if decision.permission == ToolPermission.BLOCK:
            assert "credential" not in (decision.reason or "").lower(), (
                f"Same delegation blocked for credential isolation: "
                f"ctx={ctx}, tool={name}"
            )

    @given(
        name=tool_name_st,
    )
    @pytest.mark.asyncio
    async def test_no_credential_context_allowed(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
    ) -> None:
        """No credential context → allowed (new delegation)."""
        context = _make_context()  # no delegation_id set
        tool_call = _make_tool_call(name=name)  # no credential_context

        decision = await evaluator.evaluate(tool_call, context)

        # Should never be blocked due to credential isolation
        if decision.permission == ToolPermission.BLOCK:
            assert "credential" not in (decision.reason or "").lower()

    @given(
        name=tool_name_st,
        tool_ctx=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
    )
    @pytest.mark.asyncio
    async def test_credential_context_no_session(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        tool_ctx: str,
    ) -> None:
        """Credential context set but session has no delegation → not blocked by credential isolation."""
        context = _make_context()
        context.audit_metadata.pop("delegation_id", None)
        tool_call = _make_tool_call(name=name, credential_context=tool_ctx)

        decision = await evaluator.evaluate(tool_call, context)

        if decision.permission == ToolPermission.BLOCK:
            assert "credential" not in (decision.reason or "").lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. No raw values in audit events
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditNoRawValuesProperty:
    """Audit events never contain PII, token patterns, or raw arguments.

    Invariant: ``_TO_DICT`` output of a ``ToolAuditEvent`` must never
    include keys listed in ``FORBIDDEN_AUDIT_KEYS``.  Additionally,
    the serialised output should not contain raw argument content,
    token placeholders, or known PII patterns.
    """

    @given(
        event_type=st.sampled_from(list(ToolAuditEventType)),
        permission=st.sampled_from(list(ToolPermission)),
        risk=st.one_of(st.none(), st.sampled_from(list(ToolRiskLevel))),
        domain=st.sampled_from(_DOMAINS),
        provider=st.sampled_from(_PROVIDERS),
        tool_name=tool_name_st,
    )
    def test_to_dict_forbidden_keys(
        self,
        event_type: ToolAuditEventType,
        permission: ToolPermission,
        risk: ToolRiskLevel | None,
        domain: str,
        provider: str,
        tool_name: str,
    ) -> None:
        """No FORBIDDEN_AUDIT_KEYS leak into the serialised event."""
        event = ToolAuditEvent(
            event_type=event_type,
            tool_name=tool_name,
            provider=provider,
            domain=domain,
            permission=permission.value if permission else None,
            risk_level=risk.value if risk else None,
        )
        result = tool_audit_event_to_dict(event)
        for key in result:
            assert key not in FORBIDDEN_AUDIT_KEYS, (
                f"Forbidden key '{key}' leaked into audit output "
                f"for event {event_type}"
            )

    @given(
        event_type=st.sampled_from(list(ToolAuditEventType)),
        permission=st.sampled_from(list(ToolPermission)),
        tool_name=tool_name_st,
    )
    def test_no_token_patterns_in_audit(
        self,
        event_type: ToolAuditEventType,
        permission: ToolPermission,
        tool_name: str,
    ) -> None:
        """Audit serialisation output never contains ``[TYPE_N]`` patterns."""
        event = ToolAuditEvent(
            event_type=event_type,
            tool_name=tool_name,
            provider="openai",
            domain="model",
            permission=permission.value,
        )
        result = tool_audit_event_to_dict(event)

        import re
        token_pattern = re.compile(r"\[[A-Z]+_\d+\]")
        for key, value in result.items():
            if isinstance(value, str):
                assert not token_pattern.search(value), (
                    f"Token pattern found in audit field '{key}': {value!r}"
                )

    @given(
        event_type=st.sampled_from(list(ToolAuditEventType)),
        permission=st.sampled_from(list(ToolPermission)),
        tool_name=tool_name_st,
    )
    def test_no_pii_values_in_audit(
        self,
        event_type: ToolAuditEventType,
        permission: ToolPermission,
        tool_name: str,
    ) -> None:
        """Audit output never contains raw PII-looking values.

        We check that string values do not look like email addresses,
        phone numbers, or credit card numbers.
        """
        event = ToolAuditEvent(
            event_type=event_type,
            tool_name=tool_name,
            provider="openai",
            domain="model",
            permission=permission.value,
        )
        result = tool_audit_event_to_dict(event)

        import re
        email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
        phone_re = re.compile(r"\+?\d{7,}")
        cc_re = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")

        for key, value in result.items():
            if isinstance(value, str):
                assert not email_re.search(value), (
                    f"Email-like value in audit field '{key}': {value!r}"
                )
                assert not phone_re.search(value), (
                    f"Phone-like value in audit field '{key}': {value!r}"
                )
                assert not cc_re.search(value), (
                    f"Credit-card-like value in audit field '{key}': {value!r}"
                )

    @given(
        event_type=st.sampled_from(list(ToolAuditEventType)),
        permission=st.sampled_from(list(ToolPermission)),
        tool_name=tool_name_st,
    )
    def test_emit_audit_event_no_forbidden_keys(
        self,
        event_type: ToolAuditEventType,
        permission: ToolPermission,
        tool_name: str,
    ) -> None:
        """Emitted audit event does not carry forbidden keys."""
        from unittest.mock import MagicMock

        logger = MagicMock()
        event = ToolAuditEvent(
            event_type=event_type,
            tool_name=tool_name,
            provider="openai",
            domain="model",
            permission=permission.value,
        )
        emit_tool_audit_event(event, logger)

        _, kwargs = logger.info.call_args
        for key in kwargs:
            assert key not in FORBIDDEN_AUDIT_KEYS, (
                f"Forbidden key '{key}' in emitted event kwargs"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Low-risk unlisted → default ALLOW
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnlistedLowRiskDefaultAllow:
    """Unlisted LOW risk tool defaults to ALLOW.

    Invariant: a tool name not in any policy but classified as LOW risk
    (through an empty classification map) must return ALLOW.
    """

    @given(
        name=unknown_tool_name_st,
    )
    @pytest.mark.asyncio
    async def test_unlisted_low_risk_default_allow(
        self,
        parser: ToolPolicyParser,
        name: str,
    ) -> None:
        """Unlisted tool with no risk classification → ALLOW."""
        # Create a mini parser with empty classification and no tools
        mini_parser = ToolPolicyParser()
        mini_parser.parse({
            "providers": {
                "openai": {
                    "tool_risk_classification": {},
                    "tools": [],
                },
            },
        })
        mini_eval = PDPToolEvaluator(mini_parser)

        context = _make_context()
        tool_call = _make_tool_call(name=name, provider="openai", domain="model")

        decision = await mini_eval.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.ALLOW, (
            f"Unlisted tool '{name}' got {decision.permission}, expected ALLOW"
        )

    @given(
        name=unknown_tool_name_st,
    )
    @pytest.mark.asyncio
    async def test_unlisted_critical_risk_needs_approval(
        self,
        name: str,
    ) -> None:
        """Tool classified as CRITICAL but not in tools list → REQUIRE_HUMAN_APPROVAL."""
        mini_parser = ToolPolicyParser()
        mini_parser.parse({
            "providers": {
                "openai": {
                    "tool_risk_classification": {
                        "some_critical_tool": "critical",
                    },
                    "tools": [],
                },
            },
        })
        mini_eval = PDPToolEvaluator(mini_parser)

        context = _make_context()
        # The tool must match the classification key for CRITICAL risk to apply
        tool_call = _make_tool_call(
            name="some_critical_tool", provider="openai", domain="model",
        )

        decision = await mini_eval.evaluate(tool_call, context)

        assert decision.permission == ToolPermission.REQUIRE_HUMAN_APPROVAL, (
            f"Unlisted CRITICAL tool 'some_critical_tool' got "
            f"{decision.permission}, expected REQUIRE_HUMAN_APPROVAL"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Extra: Tool result validation invariants
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolResultProperty:
    """Tool result invariants under property test."""

    @given(
        tool_id=st.text(min_size=1, max_size=20),
        tool_name=tool_name_st,
        is_error=st.booleans(),
        fmt=format_st,
    )
    def test_tool_result_always_adds_audit_key(
        self,
        evaluator: PDPToolEvaluator,
        tool_id: str,
        tool_name: str,
        is_error: bool,
        fmt: str,
    ) -> None:
        """Every tool result evaluation adds an audit metadata entry."""
        context = _make_context()
        result = ToolResult(
            id=tool_id,
            name=tool_name,
            content="result content",
            format=fmt,
            is_error=is_error,
        )

        evaluator.evaluate_tool_result(result, context)

        audit_key = f"tool_result_{tool_id}"
        assert audit_key in context.audit_metadata, (
            f"Missing audit key '{audit_key}' for tool result {tool_id}"
        )
        meta = context.audit_metadata[audit_key]
        assert meta["tool_id"] == tool_id
        assert meta["is_error"] == is_error

    @given(
        tool_id=st.text(min_size=1, max_size=20),
        tool_name=tool_name_st,
        is_error=st.booleans(),
        fmt=format_st,
    )
    def test_tool_result_audit_no_raw_content(
        self,
        evaluator: PDPToolEvaluator,
        tool_id: str,
        tool_name: str,
        is_error: bool,
        fmt: str,
    ) -> None:
        """Tool result audit metadata never contains raw content."""
        context = _make_context()
        result = ToolResult(
            id=tool_id,
            name=tool_name,
            content="sensitive-user-content-that-should-not-leak",
            format=fmt,
            is_error=is_error,
        )

        evaluator.evaluate_tool_result(result, context)

        audit_key = f"tool_result_{tool_id}"
        meta = context.audit_metadata[audit_key]
        for value in meta.values():
            assert isinstance(value, (str, bool)), (
                f"Unexpected type in audit metadata: {type(value)}"
            )
            if isinstance(value, str):
                assert "sensitive-user-content" not in value, (
                    f"Raw content leaked into audit metadata: {value!r}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Extra: fail-secure invariants
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailSecureProperty:
    """BLOCK decisions always add errors to context (fail-secure)."""

    @given(
        name=tool_name_st,
        provider=provider_st,
        domain=domain_st,
    )
    @pytest.mark.asyncio
    async def test_block_adds_error(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
        domain: str,
    ) -> None:
        """Whenever evaluate returns BLOCK, context has at least one error."""
        context = _make_context()
        tool_call = _make_tool_call(name=name, provider=provider, domain=domain)

        decision = await evaluator.evaluate(tool_call, context)

        if decision.permission == ToolPermission.BLOCK:
            assert context.has_errors(), (
                f"BLOCK decision for {name}@{provider}/{domain} "
                f"did not add errors to context"
            )
            assert any(
                isinstance(e, ToolBlockedError) for e in context.errors
            ), (
                f"BLOCK decision for {name}@{provider}/{domain} "
                f"did not include ToolBlockedError"
            )

    @given(
        name=tool_name_st,
        provider=provider_st,
        domain=domain_st,
    )
    @pytest.mark.asyncio
    async def test_non_block_no_error(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
        domain: str,
    ) -> None:
        """Non-BLOCK decisions do not add ToolBlockedError to context."""
        context = _make_context()
        tool_call = _make_tool_call(name=name, provider=provider, domain=domain)

        decision = await evaluator.evaluate(tool_call, context)

        if decision.permission != ToolPermission.BLOCK:
            assert not any(
                isinstance(e, ToolBlockedError) for e in context.errors
            ), (
                f"Non-BLOCK decision ({decision.permission}) for "
                f"{name}@{provider}/{domain} added ToolBlockedError"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Extra: REQUIRE_HUMAN_APPROVAL sets context flag
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiresApprovalProperty:
    """REQUIRE_HUMAN_APPROVAL always sets context.requires_approval."""

    @given(
        name=tool_name_st,
        provider=provider_st,
        domain=domain_st,
    )
    @pytest.mark.asyncio
    async def test_require_human_approval_sets_flag(
        self,
        evaluator: PDPToolEvaluator,
        name: str,
        provider: str,
        domain: str,
    ) -> None:
        context = _make_context()
        tool_call = _make_tool_call(name=name, provider=provider, domain=domain)

        decision = await evaluator.evaluate(tool_call, context)

        if decision.permission == ToolPermission.REQUIRE_HUMAN_APPROVAL:
            assert context.requires_approval is True, (
                f"REQUIRE_HUMAN_APPROVAL for {name}@{provider}/{domain} "
                f"did not set requires_approval flag"
            )
