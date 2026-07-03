"""Phase 8 policy YAML extension: per-provider tool governance policy parser.

Provides the data models and parser for tool permission policies defined
as a ``tools:`` section in the Phase 8 policy YAML configuration.

Per D-001, D-002, D-003, D-015, D-017:
- Tool policies are defined as a Phase 8 policy YAML extension (tools section)
- 4-tier permissions: ALLOW, ALLOW_WITH_AUDIT, REQUIRE_HUMAN_APPROVAL, BLOCK
- 4-tier risk classification: LOW, MEDIUM, HIGH, CRITICAL
- Tool name pattern matching: exact > prefix > glob
- Per-provider governance policies (not per-tool)
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolPermission(str, Enum):
    """Four-tier tool permission model.

    Per D-002:
    - ALLOW: tool call forwarded without restriction
    - ALLOW_WITH_AUDIT: tool call forwarded and audited
    - REQUIRE_HUMAN_APPROVAL: tool call suspended for human approval
    - BLOCK: tool call rejected with HTTP 403
    """

    ALLOW = "allow"
    ALLOW_WITH_AUDIT = "allow_with_audit"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    BLOCK = "block"


class ToolRiskLevel(str, Enum):
    """Four-tier tool risk classification.

    Per D-017:
    - LOW: read-only, no sensitive data
    - MEDIUM: read access to structured data
    - HIGH: write access or sensitive data
    - CRITICAL: destructive operations, data exfiltration risk
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolPolicyValidationError(Exception):
    """Raised when tool policy configuration is invalid.

    Validation errors indicate malformed YAML that cannot be safely
    applied — consistent with fail-secure principles (Rule 2).
    """


@dataclass
class ToolPolicy:
    """Policy definition for a single tool.

    Attributes:
        tool_name: Name of the tool (supports glob/prefix/exact matching).
        permission: One of the 4-tier permission levels.
        risk_level: Risk classification (optional, may be inherited).
        allowed_parameters: Parameter allowlist (None = all allowed).
        excluded_parameters: Parameter blocklist (None = none excluded).
        max_arguments_size: Max JSON argument size in bytes (None = no limit).
    """

    tool_name: str
    permission: ToolPermission
    risk_level: ToolRiskLevel | None = None
    allowed_parameters: list[str] | None = None
    excluded_parameters: list[str] | None = None
    max_arguments_size: int | None = None


@dataclass
class ProviderToolPolicy:
    """Policy definition for a single provider's tools.

    Per D-015: governance policies are per-provider, not per-tool.
    Each AI provider has an independent governance policy.

    Per D-018, D-019, D-020: tools are separated by domain
    (model vs host) with independent policy sets.

    Attributes:
        provider: Provider identifier (e.g. "openai", "anthropic", "host_mcp").
        domain: Tool domain — "model" or "host".
        tools: List of per-tool policy definitions.
        governance: Per-provider governance metadata (credentials, scope, etc.).
        risk_classification: Tool risk classification mapping (tool_name -> risk_level).
    """

    provider: str
    domain: str = "model"
    tools: list[ToolPolicy] = field(default_factory=list)
    governance: dict[str, Any] | None = None
    risk_classification: dict[str, ToolRiskLevel] | None = None

    def get_tool_policy(self, tool_name: str) -> ToolPolicy | None:
        """Find matching tool policy using exact > prefix > glob priority.

        Args:
            tool_name: Name of the tool to look up.

        Returns:
            The matching ToolPolicy, or None if no match found.
        """
        # Priority 1: exact match
        for tool in self.tools:
            if tool.tool_name == tool_name:
                return tool

        # Priority 2: prefix match (tool_name ends with *)
        for tool in self.tools:
            pattern = tool.tool_name
            if pattern.endswith("*") and tool_name.startswith(pattern[:-1]):
                return tool

        # Priority 3: glob match
        for tool in self.tools:
            if fnmatch.fnmatch(tool_name, tool.tool_name):
                return tool

        return None


HOST_PROVIDER_PREFIXES: set[str] = {
    "host_",
}

MODEL_DOMAIN_PROVIDERS: set[str] = {
    "openai",
    "anthropic",
    "gemini",
    "ollama",
}

VALID_PERMISSIONS: set[str] = {p.value for p in ToolPermission}
VALID_RISK_LEVELS: set[str] = {r.value for r in ToolRiskLevel}


def _detect_domain(provider: str) -> str:
    """Detect tool domain based on provider name.

    Providers starting with ``host_`` are treated as host domain.
    Known model providers are treated as model domain.
    Unknown providers default to model domain.

    Args:
        provider: Provider identifier string.

    Returns:
        "host" or "model".
    """
    if provider.startswith(tuple(HOST_PROVIDER_PREFIXES)):
        return "host"
    if provider.lower() in MODEL_DOMAIN_PROVIDERS:
        return "model"
    # Default to model for unknown providers
    return "model"


class ToolPolicyParser:
    """Parser for the Phase 8 policy YAML ``tools:`` extension.

    Parses per-provider tool governance policies from the Phase 8
    policy YAML configuration. The parser is a pure function — no I/O.
    YAML loading is handled by the Phase 8 config loader.
    """

    def __init__(self) -> None:
        self._parsed_policies: dict[str, ProviderToolPolicy] = {}

    def parse(self, policy_yaml: dict[str, Any]) -> list[ProviderToolPolicy]:
        """Parse the tools section from Phase 8 policy YAML.

        Args:
            policy_yaml: Loaded YAML configuration as a dict.

        Returns:
            List of ProviderToolPolicy objects.

        Raises:
            ToolPolicyValidationError: If the configuration is invalid.
        """
        self._parsed_policies = {}
        providers = policy_yaml.get("providers")
        if not isinstance(providers, dict):
            return []

        result: list[ProviderToolPolicy] = []

        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue

            if not provider_name or not isinstance(provider_name, str):
                raise ToolPolicyValidationError(
                    f"Invalid provider name: '{provider_name}'"
                )

            tools_data = provider_config.get("tools")
            if tools_data is None:
                continue

            domain = _detect_domain(provider_name)

            # Parse risk classification if present
            risk_classification: dict[str, ToolRiskLevel] | None = None
            raw_risk = provider_config.get("tool_risk_classification")
            if isinstance(raw_risk, dict):
                risk_classification = {}
                for tool_name, risk_str in raw_risk.items():
                    if not isinstance(risk_str, str):
                        continue
                    risk_str_lower = risk_str.lower()
                    if risk_str_lower not in VALID_RISK_LEVELS:
                        raise ToolPolicyValidationError(
                            f"Invalid risk level '{risk_str}' for tool "
                            f"'{tool_name}' in provider '{provider_name}'. "
                            f"Must be one of: {', '.join(sorted(VALID_RISK_LEVELS))}"
                        )
                    risk_classification[tool_name] = ToolRiskLevel(risk_str_lower)

            # Parse governance metadata
            governance = provider_config.get("governance")

            # Parse individual tool policies
            tools_list: list[ToolPolicy] = []
            if isinstance(tools_data, list):
                for tool_entry in tools_data:
                    if not isinstance(tool_entry, dict):
                        continue
                    tool_policy = self._parse_tool_entry(
                        tool_entry, provider_name
                    )
                    if tool_policy is not None:
                        tools_list.append(tool_policy)

            provider_policy = ProviderToolPolicy(
                provider=provider_name,
                domain=domain,
                tools=tools_list,
                governance=governance,
                risk_classification=risk_classification,
            )
            self._parsed_policies[f"{provider_name}:{domain}"] = provider_policy
            result.append(provider_policy)

        return result

    def _parse_tool_entry(
        self,
        entry: dict[str, Any],
        provider_name: str,
    ) -> ToolPolicy | None:
        """Parse a single tool policy entry from YAML.

        Args:
            entry: Tool configuration dict.
            provider_name: Provider name for error messages.

        Returns:
            Parsed ToolPolicy or None if entry is malformed.

        Raises:
            ToolPolicyValidationError: If required fields are missing or invalid.
        """
        tool_name = entry.get("name")
        if not tool_name or not isinstance(tool_name, str):
            raise ToolPolicyValidationError(
                f"Missing or invalid 'name' field in tool policy "
                f"for provider '{provider_name}'"
            )

        permission_str = entry.get("permission")
        if not permission_str or not isinstance(permission_str, str):
            raise ToolPolicyValidationError(
                f"Missing or invalid 'permission' field for tool "
                f"'{tool_name}' in provider '{provider_name}'"
            )

        permission_lower = permission_str.lower()
        if permission_lower not in VALID_PERMISSIONS:
            raise ToolPolicyValidationError(
                f"Invalid permission '{permission_str}' for tool "
                f"'{tool_name}' in provider '{provider_name}'. "
                f"Must be one of: {', '.join(sorted(VALID_PERMISSIONS))}"
            )

        # Parse optional risk level if directly specified on the tool
        risk_level: ToolRiskLevel | None = None
        risk_str = entry.get("risk_level")
        if risk_str is not None and isinstance(risk_str, str):
            risk_str_lower = risk_str.lower()
            if risk_str_lower not in VALID_RISK_LEVELS:
                raise ToolPolicyValidationError(
                    f"Invalid risk level '{risk_str}' for tool "
                    f"'{tool_name}' in provider '{provider_name}'. "
                    f"Must be one of: {', '.join(sorted(VALID_RISK_LEVELS))}"
                )
            risk_level = ToolRiskLevel(risk_str_lower)

        # Parse optional parameter rules
        allowed_params = entry.get("allowed_parameters")
        if allowed_params is not None and not isinstance(allowed_params, list):
            allowed_params = None

        excluded_params = entry.get("excluded_parameters")
        if excluded_params is not None and not isinstance(excluded_params, list):
            excluded_params = None

        max_args_size = entry.get("max_arguments_size")
        if max_args_size is not None and not isinstance(max_args_size, (int, float)):
            max_args_size = None
        if max_args_size is not None:
            max_args_size = int(max_args_size)

        return ToolPolicy(
            tool_name=tool_name,
            permission=ToolPermission(permission_lower),
            risk_level=risk_level,
            allowed_parameters=allowed_params,
            excluded_parameters=excluded_params,
            max_arguments_size=max_args_size,
        )

    def get_provider_policy(
        self,
        provider: str,
        domain: str,
    ) -> ProviderToolPolicy | None:
        """Get the full provider policy for a provider+domain pair.

        Returns the ``ProviderToolPolicy`` containing the tools list,
        risk classification map, and governance metadata, or ``None``
        if the provider+domain is not loaded.

        Args:
            provider: Provider identifier.
            domain: Tool domain ("model" or "host").
        """
        key = f"{provider}:{domain}"
        return self._parsed_policies.get(key)

    def get_policy(
        self,
        provider: str,
        domain: str,
        tool_name: str,
    ) -> ToolPolicy | None:
        """Get the matching tool policy for a provider+domain+tool.

        Uses pattern matching with priority: exact > prefix > glob.

        Args:
            provider: Provider identifier.
            domain: Tool domain ("model" or "host").
            tool_name: Name of the tool to look up.

        Returns:
            Matching ToolPolicy or None if not found.
        """
        key = f"{provider}:{domain}"
        provider_policy = self._parsed_policies.get(key)
        if provider_policy is None:
            return None
        return provider_policy.get_tool_policy(tool_name)

    def validate(self, policy_yaml: dict[str, Any]) -> list[str]:
        """Validate tool policy configuration without parsing.

        Returns a list of validation error messages. An empty list
        means the configuration is valid.

        Args:
            policy_yaml: Loaded YAML configuration as a dict.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        providers = policy_yaml.get("providers")

        if not isinstance(providers, dict):
            return errors

        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue

            if not provider_name or not isinstance(provider_name, str):
                errors.append(f"Invalid provider name: '{provider_name}'")
                continue

            tools_data = provider_config.get("tools")
            if tools_data is None:
                continue

            if not isinstance(tools_data, list):
                errors.append(
                    f"Provider '{provider_name}': 'tools' must be a list"
                )
                continue

            # Validate risk classifications
            raw_risk = provider_config.get("tool_risk_classification")
            if isinstance(raw_risk, dict):
                for tool_name, risk_str in raw_risk.items():
                    if isinstance(risk_str, str) and risk_str.lower() not in VALID_RISK_LEVELS:
                        errors.append(
                            f"Provider '{provider_name}': invalid risk level "
                            f"'{risk_str}' for tool '{tool_name}'"
                        )

            for i, tool_entry in enumerate(tools_data):
                if not isinstance(tool_entry, dict):
                    errors.append(
                        f"Provider '{provider_name}', tools[{i}]: "
                        f"expected dict, got {type(tool_entry).__name__}"
                    )
                    continue

                tool_name = tool_entry.get("name")
                if not tool_name or not isinstance(tool_name, str):
                    errors.append(
                        f"Provider '{provider_name}', tools[{i}]: "
                        f"missing or invalid 'name'"
                    )
                    continue

                permission = tool_entry.get("permission")
                if not permission or not isinstance(permission, str):
                    errors.append(
                        f"Provider '{provider_name}', tool "
                        f"'{tool_name}': missing or invalid 'permission'"
                    )
                    continue

                if permission.lower() not in VALID_PERMISSIONS:
                    errors.append(
                        f"Provider '{provider_name}', tool "
                        f"'{tool_name}': invalid permission '{permission}'"
                    )

        return errors
