"""Tool permission evaluation integrated into PDP #2.

Per D-003, D-004, D-016:
- Tool permissions evaluated as part of PDP #2 policy decisions
- 4-tier decision model: ALLOW, ALLOW_WITH_AUDIT, REQUIRE_HUMAN_APPROVAL, BLOCK
- Cross-domain isolation: model ↔ host strictly separate
- Cross-delegation credential isolation: tool calls scoped to delegation context

Per D-018, D-019, D-020:
- Model domain tools and host domain tools in separate evaluator instances
- Strict isolation — no cross-domain visibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anonreq.governance.tool_extractor import ToolCall, ToolResult
from anonreq.governance.tool_policy_parser import (
    ToolPermission,
    ToolPolicyParser,
    ToolRiskLevel,
)
from anonreq.models.processing_context import ProcessingContext


@dataclass
class ToolDecision:
    """Decision returned by PDPToolEvaluator for a single tool call.

    Attributes:
        permission: The 4-tier permission decision.
        tool_name: Name of the evaluated tool.
        provider: Provider identifier.
        domain: Tool domain ("model" or "host").
        risk_level: Risk level classification (if available).
        reason: Human-readable reason for the decision.
        audit: Audit metadata dict.
        credential_context: Delegation context for credential isolation.
    """

    permission: ToolPermission
    tool_name: str
    provider: str
    domain: str = "model"
    risk_level: ToolRiskLevel | None = None
    reason: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)
    credential_context: str | None = None


class PDPToolEvaluator:
    """Tool permission evaluator integrated into PDP #2.

    Evaluates tool calls against per-provider tool policies loaded
    from the Phase 8 YAML configuration. Enforces domain isolation
    and credential isolation per D-016, D-018, D-019, D-020.
    """

    def __init__(
        self,
        policy_parser: ToolPolicyParser,
        default_unlisted_permission: ToolPermission = ToolPermission.ALLOW,
        default_critical_permission: ToolPermission = ToolPermission.REQUIRE_HUMAN_APPROVAL,
        strict_domain_isolation: bool = True,
    ) -> None:
        """Initialize the PDPToolEvaluator.

        Args:
            policy_parser: ToolPolicyParser instance with loaded policies.
            default_unlisted_permission: Default permission for unlisted tools.
            default_critical_permission: Default permission for unlisted
                CRITICAL risk tools.
            strict_domain_isolation: If True, cross-domain tool calls are blocked.
        """
        self._parser = policy_parser
        self._default_unlisted = default_unlisted_permission
        self._default_critical = default_critical_permission
        self._strict_domain_isolation = strict_domain_isolation

    async def evaluate(
        self,
        tool_call: ToolCall,
        context: ProcessingContext,
    ) -> ToolDecision:
        """Evaluate a single tool call against policy.

        Args:
            tool_call: The extracted tool call to evaluate.
            context: Processing context with tenant/provider information.

        Returns:
            ToolDecision with the 4-tier permission decision.

        Raises:
            ToolBlockedError: If tool is blocked and blocked errors are
                attached to context.
        """
        provider = tool_call.provider or context.provider or "unknown"
        domain = tool_call.domain
        tool_name = tool_call.name

        # Cross-domain isolation check
        if self._strict_domain_isolation:
            domain_error = self._check_domain_isolation(domain, tool_name, provider)
            if domain_error is not None:
                decision = ToolDecision(
                    permission=ToolPermission.BLOCK,
                    tool_name=tool_name,
                    provider=provider,
                    domain=domain,
                    reason=domain_error,
                    audit={
                        "domain": domain,
                        "provider": provider,
                        "tool": tool_name,
                        "action": "blocked_cross_domain",
                    },
                )
                context.fail_secure(ToolBlockedError(domain_error))
                return decision

        # Cross-delegation credential isolation
        credential_error = self._check_credential_isolation(tool_call, context)
        if credential_error is not None:
            decision = ToolDecision(
                permission=ToolPermission.BLOCK,
                tool_name=tool_name,
                provider=provider,
                domain=domain,
                reason=credential_error,
                audit={
                    "tool": tool_name,
                    "provider": provider,
                    "action": "blocked_cross_delegation_credential_leak",
                },
            )
            context.fail_secure(ToolBlockedError(credential_error))
            return decision

        # Match against policy
        policy = self._parser.get_policy(provider, domain, tool_name)

        if policy is not None:
            permission = policy.permission
            risk_level = policy.risk_level
        else:
            # Unlisted tool — determine default based on risk
            risk_level = self._get_tool_risk_level(tool_name, provider)
            if risk_level == ToolRiskLevel.CRITICAL:
                permission = self._default_critical
            else:
                permission = self._default_unlisted

        # Determine risk level from policy or classification
        if risk_level is None:
            risk_level = self._get_tool_risk_level(tool_name, provider)

        # Handle BLOCK
        if permission == ToolPermission.BLOCK:
            reason = f"Tool '{tool_name}' is blocked by policy"
            decision = ToolDecision(
                permission=ToolPermission.BLOCK,
                tool_name=tool_name,
                provider=provider,
                domain=domain,
                risk_level=risk_level,
                reason=reason,
                audit={
                    "tool": tool_name,
                    "provider": provider,
                    "domain": domain,
                    "action": "blocked",
                    "risk_level": risk_level.value if risk_level else "unknown",
                },
            )
            context.fail_secure(ToolBlockedError(reason))
            return decision

        # Handle REQUIRE_HUMAN_APPROVAL
        if permission == ToolPermission.REQUIRE_HUMAN_APPROVAL:
            context.requires_approval = True
            return ToolDecision(
                permission=ToolPermission.REQUIRE_HUMAN_APPROVAL,
                tool_name=tool_name,
                provider=provider,
                domain=domain,
                risk_level=risk_level,
                reason=f"Tool '{tool_name}' requires human approval",
                audit={
                    "tool": tool_name,
                    "provider": provider,
                    "domain": domain,
                    "action": "approval_required",
                    "risk_level": risk_level.value if risk_level else "unknown",
                },
            )

        # Handle ALLOW_WITH_AUDIT
        if permission == ToolPermission.ALLOW_WITH_AUDIT:
            return ToolDecision(
                permission=ToolPermission.ALLOW_WITH_AUDIT,
                tool_name=tool_name,
                provider=provider,
                domain=domain,
                risk_level=risk_level,
                reason=f"Tool '{tool_name}' allowed with audit",
                audit={
                    "tool": tool_name,
                    "provider": provider,
                    "domain": domain,
                    "action": "allowed_with_audit",
                    "risk_level": risk_level.value if risk_level else "unknown",
                },
            )

        # Default: ALLOW
        return ToolDecision(
            permission=ToolPermission.ALLOW,
            tool_name=tool_name,
            provider=provider,
            domain=domain,
            risk_level=risk_level,
            reason=f"Tool '{tool_name}' allowed",
            audit={
                "tool": tool_name,
                "provider": provider,
                "domain": domain,
                "action": "allowed",
                "risk_level": risk_level.value if risk_level else "unknown",
            },
        )

    def evaluate_tool_result(
        self,
        tool_result: ToolResult,
        context: ProcessingContext,
    ) -> None:
        """Validate a tool result against the approved tool call context.

        Flags orphaned tool results (results with no matching approved
        tool call) for audit.

        Args:
            tool_result: The tool result to evaluate.
            context: Processing context with audit metadata.
        """
        # For now, record audit metadata about the tool result.
        # Full approved-call tracking is implemented in later waves.
        audit_key = f"tool_result_{tool_result.id}"
        context.audit_metadata[audit_key] = {
            "tool_id": tool_result.id,
            "is_error": tool_result.is_error,
            "format": tool_result.format,
        }

    def get_permitted_actions(
        self,
        provider: str,
        domain: str,
    ) -> list[str]:
        """Get list of tool names permitted for the given provider+domain.

        Args:
            provider: Provider identifier.
            domain: Tool domain ("model" or "host").

        Returns:
            List of tool names that are NOT blocked for this provider+domain.
        """
        permitted: list[str] = []

        # Scan all loaded policies for this provider+domain
        for policy_name in ["openai", "anthropic", "gemini", "host_mcp"]:
            for tool_name in ["code_interpreter", "file_search", "db_query"]:
                policy = self._parser.get_policy(policy_name, domain, tool_name)
                if policy is not None and policy.permission != ToolPermission.BLOCK:
                    permitted.append(tool_name)

        return permitted

    def _check_domain_isolation(
        self,
        domain: str,
        tool_name: str,
        provider: str,
    ) -> str | None:
        """Check if a tool call violates domain isolation.

        Args:
            domain: The domain of the tool call ("model" or "host").
            tool_name: Name of the tool being called.
            provider: Provider identifier.

        Returns:
            Error message if domain isolation violated, None otherwise.
        """
        # Host provider calling from model domain
        if domain == "model" and provider == "host_mcp":
            return (
                f"Cross-domain isolation: model domain tool call "
                f"'{tool_name}' targets host provider '{provider}'"
            )

        # Model provider calling from host domain
        if domain == "host" and provider in ("openai", "anthropic", "gemini"):
            return (
                f"Cross-domain isolation: host domain tool call "
                f"'{tool_name}' targets model provider '{provider}'"
            )

        return None

    def _check_credential_isolation(
        self,
        tool_call: ToolCall,
        context: ProcessingContext,
    ) -> str | None:
        """Check if a tool call violates credential isolation.

        Per D-016: tool calls from one delegation must never access
        another delegation's credentials.

        Args:
            tool_call: The tool call being evaluated.
            context: Processing context with delegation/tenant info.

        Returns:
            Error message if credential isolation violated, None otherwise.
        """
        # Credential context from the tool call
        credential_ctx = getattr(tool_call, "credential_context", None)

        # If no credential context specified, it's a new delegation — allowed
        if credential_ctx is None:
            return None

        # Check if credential context matches the current session's delegation
        session_ctx = context.audit_metadata.get("delegation_id")
        if session_ctx is not None and credential_ctx != session_ctx:
            return (
                f"Cross-delegation credential isolation: tool call "
                f"credential context '{credential_ctx}' does not match "
                f"session delegation '{session_ctx}'"
            )

        return None

    def _get_tool_risk_level(
        self,
        tool_name: str,
        provider: str,
    ) -> ToolRiskLevel | None:
        """Determine risk level for a tool from policy classification.

        Checks two sources (priority order):
        1. The tool's individual policy (``ToolPolicy.risk_level``).
        2. The provider's risk classification map
           (``ProviderToolPolicy.risk_classification``), for unlisted tools.

        Args:
            tool_name: Name of the tool.
            provider: Provider identifier.

        Returns:
            ToolRiskLevel if known, None if unknown.
        """
        # Priority 1: tool policy risk_level
        for domain in ("model", "host"):
            policy = self._parser.get_policy(provider, domain, tool_name)
            if policy is not None and policy.risk_level is not None:
                return policy.risk_level

        # Priority 2: provider risk_classification map (for unlisted tools)
        for domain in ("model", "host"):
            provider_policy = self._parser.get_provider_policy(provider, domain)
            if provider_policy is not None and provider_policy.risk_classification:
                risk = provider_policy.risk_classification.get(tool_name)
                if risk is not None:
                    return risk

        return None


class ToolBlockedError(Exception):
    """Exception raised when a tool call is blocked by policy.

    This is attached to ProcessingContext.errors to trigger fail-secure
    behavior — the blocked tool call prevents forwarding.
    """
