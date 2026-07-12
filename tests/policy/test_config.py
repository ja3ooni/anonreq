"""Tests for policy YAML config loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from anonreq.policy.config import PolicyConfig, load_policy_config, validate_policy_bundle
from anonreq.policy.models import PolicyAction


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return path


class TestLoadPolicyConfig:
    def test_loads_valid_minimal_config(self, tmp_path):
        cfg_path = _write_yaml(tmp_path / "policy.yaml", {
            "version": "1.0",
            "rules": [
                {"rule_id": "rule-1", "name": "Test Rule", "action": "BLOCK"},
            ],
        })
        cfg = load_policy_config(cfg_path)
        assert cfg.version == "1.0"
        assert len(cfg.rules) == 1
        assert cfg.rules[0].action == PolicyAction.BLOCK
        assert cfg.default_action == PolicyAction.ALLOW

    def test_loads_full_config(self, tmp_path):
        cfg_path = _write_yaml(tmp_path / "policy.yaml", {
            "version": "2.0",
            "tenant_id": "tenant_acme",
            "default_action": "MONITOR",
            "rules": [
                {"rule_id": "r1", "name": "Rule 1", "action": "BLOCK", "priority": 100},
                {"rule_id": "r2", "name": "Rule 2", "action": "ALLOW", "priority": 0},
            ],
            "rate_limits": {"rpm": 500, "tpm": 50000, "concurrent": 25, "enabled": True},
            "spend_budgets": {"tenant_acme": {"daily_usd": 100, "monthly_usd": 3000}},
            "residency_rules": {
                "tenant_acme": {
                    "allowed_regions": ["us-east-1"],
                    "blocked_regions": ["cn-north-1"],
                    "fallback_action": "BLOCK",
                }
            },
        })
        cfg = load_policy_config(cfg_path)
        assert cfg.version == "2.0"
        assert cfg.tenant_id == "tenant_acme"
        assert cfg.default_action == PolicyAction.MONITOR
        assert len(cfg.rules) == 2
        assert cfg.rate_limits is not None
        assert cfg.rate_limits.rpm == 500
        assert "tenant_acme" in cfg.spend_budgets
        assert cfg.spend_budgets["tenant_acme"].daily_usd == 100
        assert "tenant_acme" in cfg.residency_rules
        assert cfg.residency_rules["tenant_acme"].fallback_action == PolicyAction.BLOCK

    def test_missing_file_raises_filenotfound(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError) as exc:
            load_policy_config(missing)
        assert str(missing) in str(exc.value)

    def test_invalid_yaml_syntax_raises_error(self, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        with open(bad_yaml, "w") as f:
            f.write("version: [unclosed\n")
        with pytest.raises(yaml.YAMLError):
            load_policy_config(bad_yaml)

    def test_malformed_structure_raises_validation_error(self, tmp_path):
        cfg_path = _write_yaml(tmp_path / "policy.yaml", {
            "version": "1.0",
            "rules": [{"rule_id": "r1", "action": "NOT_A_VALID_ACTION"}],
        })
        with pytest.raises(ValidationError):
            load_policy_config(cfg_path)

    def test_empty_required_fields_raises_validation_error(self, tmp_path):
        cfg_path = _write_yaml(tmp_path / "policy.yaml", {
            "version": "1.0",
            "rules": [{"rule_id": "", "action": "ALLOW"}],
        })
        with pytest.raises(ValidationError):
            load_policy_config(cfg_path)

    def test_explicit_path_overrides_default(self, tmp_path):
        default_path = tmp_path / "policy.yaml"
        explicit_path = tmp_path / "custom.yaml"
        _write_yaml(default_path, {"version": "1.0", "rules": [{"rule_id": "d1", "action": "BLOCK"}]})  # noqa: E501
        _write_yaml(explicit_path, {"version": "2.0", "rules": [{"rule_id": "c1", "action": "ALLOW"}]})  # noqa: E501
        cfg = load_policy_config(explicit_path)
        assert cfg.version == "2.0"
        assert cfg.rules[0].rule_id == "c1"

    def test_version_field_preserved(self, tmp_path):
        cfg_path = _write_yaml(tmp_path / "policy.yaml", {
            "version": "3.1",
            "rules": [{"rule_id": "r1", "action": "ALLOW"}],
        })
        cfg = load_policy_config(cfg_path)
        assert cfg.version == "3.1"


class TestValidatePolicyBundle:
    def test_no_warnings_for_valid_config(self):
        config = PolicyConfig(
            version="1.0",
            rules=[{"rule_id": "r1", "name": "Active", "action": "ALLOW", "enabled": True}],
            spend_budgets={},
            residency_rules={},
        )
        warnings = validate_policy_bundle(config)
        assert warnings == []

    def test_detects_duplicate_rule_ids(self):
        config = PolicyConfig(
            version="1.0",
            rules=[
                {"rule_id": "dup", "name": "First", "action": "BLOCK"},
                {"rule_id": "dup", "name": "Second", "action": "ALLOW"},
            ],
            spend_budgets={},
            residency_rules={},
        )
        warnings = validate_policy_bundle(config)
        assert any("dup" in w for w in warnings)

    def test_warns_no_enabled_rules(self):
        config = PolicyConfig(
            version="1.0",
            rules=[
                {"rule_id": "r1", "name": "Disabled", "action": "BLOCK", "enabled": False},
            ],
            spend_budgets={},
            residency_rules={},
        )
        warnings = validate_policy_bundle(config)
        assert any("enabled" in w.lower() for w in warnings)

    def test_detects_conflicting_priorities(self):
        config = PolicyConfig(
            version="1.0",
            rules=[
                {"rule_id": "r1", "name": "First", "action": "BLOCK", "priority": 50},
                {"rule_id": "r2", "name": "Second", "action": "ALLOW", "priority": 50},
            ],
            spend_budgets={},
            residency_rules={},
        )
        warnings = validate_policy_bundle(config)
        assert any("priority" in w and "50" in w for w in warnings)


class TestPolicyConfigModel:
    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            PolicyConfig(
                version="1.0",
                rules=[],
                spend_budgets={},
                residency_rules={},
                unknown_field="bad",
            )

    def test_default_action_defaults_to_allow(self):
        config = PolicyConfig(
            version="1.0",
            rules=[],
            spend_budgets={},
            residency_rules={},
        )
        assert config.default_action == PolicyAction.ALLOW
