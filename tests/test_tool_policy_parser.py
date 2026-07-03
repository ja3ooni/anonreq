"""Tests for the Phase 8 policy YAML tool governance extension.

Tests cover:
- Parsing valid tools section from Phase 8 YAML
- Per-provider tool policies with 4-tier permissions
- Tool risk classification (low/medium/high/critical)
- Invalid permission levels raise ToolPolicyValidationError
- Missing required tool fields raise ToolPolicyValidationError
- Wildcard/prefix/exact pattern matching for tool names
- Per-tool exclusion rules and parameter allowlists
"""

from __future__ import annotations

import pytest

from anonreq.governance.tool_policy_parser import (
    ToolPermission,
    ToolPolicy,
    ToolPolicyParser,
    ToolPolicyValidationError,
    ToolRiskLevel,
)


def _minimal_tools_yaml(**overrides) -> dict:
    """Build a minimal tools YAML dict for testing."""
    yaml = {
        "providers": {
            "openai": {
                "tools": [
                    {"name": "code_interpreter", "permission": "block"},
                ],
            },
        },
    }
    yaml.update(overrides)
    return yaml


class TestParseValidToolsYAML:
    """Tests for parsing valid tools YAML configurations."""

    def test_parse_valid_tools_section(self):
        """Test 1: Parse valid tools section from Phase 8 YAML."""
        parser = ToolPolicyParser()
        yaml = _minimal_tools_yaml()
        policies = parser.parse(yaml)

        assert len(policies) == 1
        assert policies[0].provider == "openai"
        assert len(policies[0].tools) == 1
        assert policies[0].tools[0].tool_name == "code_interpreter"
        assert policies[0].tools[0].permission == ToolPermission.BLOCK

    def test_parse_per_provider_4_tier_permissions(self):
        """Test 2: Parse per-provider tool policies with all 4 permission tiers."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "read_tool", "permission": "allow"},
                        {"name": "audit_tool", "permission": "allow_with_audit"},
                        {"name": "approval_tool", "permission": "require_human_approval"},
                        {"name": "block_tool", "permission": "block"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)

        assert len(policies) == 1
        tools = {t.tool_name: t.permission for t in policies[0].tools}
        assert tools["read_tool"] == ToolPermission.ALLOW
        assert tools["audit_tool"] == ToolPermission.ALLOW_WITH_AUDIT
        assert tools["approval_tool"] == ToolPermission.REQUIRE_HUMAN_APPROVAL
        assert tools["block_tool"] == ToolPermission.BLOCK

    def test_parse_risk_classification(self):
        """Test 3: Parse tool risk classification (low/medium/high/critical)."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tool_risk_classification": {
                        "safe_tool": "low",
                        "read_tool": "medium",
                        "write_tool": "high",
                        "destroy_tool": "critical",
                    },
                    "tools": [
                        {"name": "safe_tool", "permission": "allow"},
                        {"name": "destroy_tool", "permission": "block"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)

        risk_map = policies[0].risk_classification
        assert risk_map is not None
        assert risk_map["safe_tool"] == ToolRiskLevel.LOW
        assert risk_map["read_tool"] == ToolRiskLevel.MEDIUM
        assert risk_map["write_tool"] == ToolRiskLevel.HIGH
        assert risk_map["destroy_tool"] == ToolRiskLevel.CRITICAL

    def test_parse_governance_config(self):
        """Parse governance metadata per-provider."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "governance": {
                        "credentials": "per_delegation",
                        "scope": "per_delegation",
                    },
                    "tools": [
                        {"name": "test", "permission": "allow"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)

        assert len(policies) == 1
        assert policies[0].governance == {
            "credentials": "per_delegation",
            "scope": "per_delegation",
        }

    def test_parse_missing_tools_section_returns_empty(self):
        """Missing tools section returns empty list (not an error)."""
        parser = ToolPolicyParser()
        yaml = {"providers": {"openai": {}}}
        policies = parser.parse(yaml)
        assert policies == []

    def test_parse_no_providers_returns_empty(self):
        """No providers at all returns empty list."""
        parser = ToolPolicyParser()
        yaml = {"version": "1.0"}
        policies = parser.parse(yaml)
        assert policies == []

    def test_parse_empty_tools_list_returns_provider_with_empty_tools(self):
        """Empty tools list for a provider returns a ProviderToolPolicy with no tools."""
        parser = ToolPolicyParser()
        yaml = {"providers": {"openai": {"tools": []}}}
        policies = parser.parse(yaml)
        assert len(policies) == 1
        assert policies[0].provider == "openai"
        assert policies[0].tools == []

    def test_parse_multiple_providers(self):
        """Parse tools for multiple providers."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [{"name": "code_interpreter", "permission": "block"}],
                },
                "host_mcp": {
                    "tools": [{"name": "db_query", "permission": "require_human_approval"}],
                },
            },
        }
        policies = parser.parse(yaml)
        assert len(policies) == 2
        provider_names = {p.provider for p in policies}
        assert provider_names == {"openai", "host_mcp"}


class TestParseInvalidConfig:
    """Tests for error handling on invalid configurations."""

    def test_invalid_permission_level_raises_error(self):
        """Test 4: Invalid permission level raises ToolPolicyValidationError."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "test_tool", "permission": "not_a_valid_permission"},
                    ],
                },
            },
        }
        with pytest.raises(ToolPolicyValidationError, match="permission"):
            parser.parse(yaml)

    def test_missing_tool_name_raises_error(self):
        """Test 5a: Missing tool name raises ToolPolicyValidationError."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"permission": "block"},
                    ],
                },
            },
        }
        with pytest.raises(ToolPolicyValidationError, match="name"):
            parser.parse(yaml)

    def test_missing_tool_permission_raises_error(self):
        """Test 5b: Missing tool permission raises ToolPolicyValidationError."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "test_tool"},
                    ],
                },
            },
        }
        with pytest.raises(ToolPolicyValidationError, match="permission"):
            parser.parse(yaml)

    def test_empty_provider_name_raises_error(self):
        """Empty provider key raises error."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "": {
                    "tools": [{"name": "test", "permission": "allow"}],
                },
            },
        }
        with pytest.raises(ToolPolicyValidationError, match="provider"):
            parser.parse(yaml)

    def test_invalid_risk_level_raises_error(self):
        """Invalid risk classification level raises ToolPolicyValidationError."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tool_risk_classification": {
                        "test_tool": "unknown_level",
                    },
                    "tools": [{"name": "test_tool", "permission": "allow"}],
                },
            },
        }
        with pytest.raises(ToolPolicyValidationError, match="risk"):
            parser.parse(yaml)


class TestGetPolicy:
    """Tests for the get_policy pattern matching."""

    def test_get_policy_exact_match(self):
        """Exact tool name match returns correct ToolPolicy."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "code_interpreter", "permission": "block"},
                        {"name": "file_search", "permission": "allow_with_audit"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "code_interpreter")

        assert policy is not None
        assert policy.tool_name == "code_interpreter"
        assert policy.permission == ToolPermission.BLOCK

    def test_get_policy_prefix_match(self):
        """Prefix pattern matching for tool names."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "file_*", "permission": "allow_with_audit"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "file_search")

        assert policy is not None
        assert policy.permission == ToolPermission.ALLOW_WITH_AUDIT

    def test_get_policy_glob_match(self):
        """Glob pattern matching for tool names."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "data.*", "permission": "block"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "data.export")

        assert policy is not None
        assert policy.permission == ToolPermission.BLOCK

    def test_get_policy_exact_over_prefix_over_glob(self):
        """Test 6: Pattern matching priority: exact > prefix > glob."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "file_*", "permission": "allow_with_audit"},
                        {"name": "file_search", "permission": "block"},
                        {"name": "file.*", "permission": "allow"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)

        # Exact match wins
        exact = parser.get_policy("openai", "model", "file_search")
        assert exact is not None
        assert exact.permission == ToolPermission.BLOCK

        # Prefix match (file_* matches file_read)
        prefix = parser.get_policy("openai", "model", "file_read")
        assert prefix is not None
        assert prefix.permission == ToolPermission.ALLOW_WITH_AUDIT

        # Glob match (file.* matches file.list)
        glob_match = parser.get_policy("openai", "model", "file.list")
        assert glob_match is not None
        assert glob_match.permission == ToolPermission.ALLOW

    def test_get_policy_none_for_unlisted(self):
        """Unlisted tool name returns None."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "code_interpreter", "permission": "block"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "unknown_tool")
        assert policy is None

    def test_get_policy_none_for_unlisted_when_block_default(self):
        """Unlisted tool returns None even when default=block policy is active."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "code_interpreter", "permission": "block"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "nonexistent")
        assert policy is None

    def test_get_policy_cross_provider_isolation(self):
        """Policies are isolated per-provider — no cross-contamination."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [{"name": "search", "permission": "allow"}],
                },
                "anthropic": {
                    "tools": [{"name": "search", "permission": "block"}],
                },
            },
        }
        policies = parser.parse(yaml)

        openai_policy = parser.get_policy("openai", "model", "search")
        anthropic_policy = parser.get_policy("anthropic", "model", "search")

        assert openai_policy is not None
        assert openai_policy.permission == ToolPermission.ALLOW
        assert anthropic_policy is not None
        assert anthropic_policy.permission == ToolPermission.BLOCK


class TestValidate:
    """Tests for the validate method."""

    def test_validate_returns_empty_for_valid(self):
        """Valid config returns empty validation errors."""
        parser = ToolPolicyParser()
        yaml = _minimal_tools_yaml()
        errors = parser.validate(yaml)
        assert errors == []

    def test_validate_returns_errors_for_malformed(self):
        """Malformed config returns validation errors."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {"name": "test", "permission": "invalid"},
                    ],
                },
            },
        }
        errors = parser.validate(yaml)
        assert len(errors) > 0
        assert any("invalid" in e.lower() for e in errors)


class TestParameterRules:
    """Tests for per-tool parameter allowlists and exclusions."""

    def test_allowed_parameters_parsed(self):
        """Test 7a: Parameter allowlists are parsed correctly."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {
                            "name": "search",
                            "permission": "allow",
                            "allowed_parameters": ["query", "max_results"],
                        },
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        tool = policies[0].tools[0]
        assert tool.allowed_parameters == ["query", "max_results"]

    def test_excluded_parameters_parsed(self):
        """Test 7b: Parameter exclusions are parsed correctly."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {
                            "name": "search",
                            "permission": "allow",
                            "excluded_parameters": ["api_key", "secret"],
                        },
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        tool = policies[0].tools[0]
        assert tool.excluded_parameters == ["api_key", "secret"]

    def test_max_arguments_size_parsed(self):
        """max_arguments_size restriction is parsed correctly."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {
                            "name": "large_tool",
                            "permission": "allow",
                            "max_arguments_size": 4096,
                        },
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        tool = policies[0].tools[0]
        assert tool.max_arguments_size == 4096

    def test_domain_field_parsed(self):
        """Domain field is parsed correctly for host vs model."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "host_mcp": {
                    "tools": [
                        {"name": "db_query", "permission": "require_human_approval"},
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        assert policies[0].domain == "host"

    def test_openai_defaults_to_model_domain(self):
        """OpenAI provider defaults to model domain."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [{"name": "search", "permission": "allow"}],
                },
            },
        }
        policies = parser.parse(yaml)
        assert policies[0].domain == "model"


class TestGetPolicyWithParamRules:
    """Tests for get_policy returning full ToolPolicy with parameter rules."""

    def test_get_policy_returns_param_rules(self):
        """get_policy returns ToolPolicy with parameter allowlist."""
        parser = ToolPolicyParser()
        yaml = {
            "providers": {
                "openai": {
                    "tools": [
                        {
                            "name": "search",
                            "permission": "allow",
                            "allowed_parameters": ["query"],
                        },
                    ],
                },
            },
        }
        policies = parser.parse(yaml)
        policy = parser.get_policy("openai", "model", "search")
        assert policy is not None
        assert policy.allowed_parameters == ["query"]
