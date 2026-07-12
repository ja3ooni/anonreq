from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from anonreq.firewall.models import DetectionCategory
from anonreq.firewall.rules import FirewallRuleLoader, load_firewall_rules


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return path


class TestFirewallRuleLoader:
    def test_load_default_rules(self):
        loader = FirewallRuleLoader("config/prompt-security-rules.yaml")
        rules = loader.load()
        assert len(rules) >= 7
        categories = {r.category for r in rules}
        assert DetectionCategory.PROMPT_INJECTION in categories
        assert DetectionCategory.JAILBREAK in categories
        assert DetectionCategory.SYSTEM_PROMPT_EXTRACTION in categories
        assert DetectionCategory.INSTRUCTION_OVERRIDE in categories
        assert DetectionCategory.ROLE_ESCALATION in categories
        assert DetectionCategory.HIDDEN_TOOL_INVOCATION in categories
        assert DetectionCategory.SECRET_EXFILTRATION in categories

    def test_each_category_has_at_least_one_rule(self):
        loader = FirewallRuleLoader("config/prompt-security-rules.yaml")
        rules = loader.load()
        for cat in DetectionCategory:
            assert any(r.category == cat for r in rules), f"Missing rule for {cat.value}"

    def test_rules_have_both_pattern_and_description(self):
        loader = FirewallRuleLoader("config/prompt-security-rules.yaml")
        rules = loader.load()
        for rule in rules:
            assert rule.pattern is not None, f"Rule {rule.rule_id} missing pattern"
            assert rule.description is not None, f"Rule {rule.rule_id} missing description"

    def test_invalid_yaml_raises(self, tmp_path: Path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{invalid: yaml: unclosed")
        loader = FirewallRuleLoader(str(bad_yaml))
        with pytest.raises(yaml.YAMLError):
            loader.load()

    def test_file_not_found_returns_empty(self, tmp_path: Path):
        loader = FirewallRuleLoader(str(tmp_path / "nonexistent.yaml"))
        rules = loader.load()
        assert rules == []

    def test_missing_required_fields_raises(self, tmp_path: Path):
        path = _write_yaml(tmp_path / "missing_fields.yaml", {
            "version": "1.0",
            "rules": [
                {"rule_id": "test-1"},
            ],
        })
        loader = FirewallRuleLoader(str(path))
        with pytest.raises(ValidationError):
            loader.load()

    def test_unknown_category_raises(self, tmp_path: Path):
        path = _write_yaml(tmp_path / "bad_category.yaml", {
            "version": "1.0",
            "rules": [
                {
                    "rule_id": "test-1",
                    "category": "unknown_category",
                    "action": "BLOCK",
                    "severity": "HIGH",
                },
            ],
        })
        loader = FirewallRuleLoader(str(path))
        with pytest.raises(ValidationError):
            loader.load()

    def test_reload_returns_updated_rules(self, tmp_path: Path):
        path = _write_yaml(tmp_path / "reloadable.yaml", {
            "version": "1.0",
            "rules": [
                {
                    "rule_id": "test-1",
                    "category": "jailbreak",
                    "action": "BLOCK",
                    "severity": "HIGH",
                    "pattern": "(?i)(test)",
                },
            ],
        })
        loader = FirewallRuleLoader(str(path))
        rules_first = loader.load()
        assert len(rules_first) == 1

        _write_yaml(path, {
            "version": "1.0",
            "rules": [
                {
                    "rule_id": "test-1",
                    "category": "jailbreak",
                    "action": "BLOCK",
                    "severity": "HIGH",
                    "pattern": "(?i)(test)",
                },
                {
                    "rule_id": "test-2",
                    "category": "prompt_injection",
                    "action": "BLOCK",
                    "severity": "HIGH",
                    "pattern": "(?i)(test2)",
                },
            ],
        })
        rules_second = loader.reload()
        assert len(rules_second) == 2

    def test_deduplication_by_rule_id(self, tmp_path: Path):
        path = _write_yaml(tmp_path / "dedup.yaml", {
            "version": "1.0",
            "rules": [
                {
                    "rule_id": "dup-1",
                    "category": "jailbreak",
                    "action": "BLOCK",
                    "severity": "HIGH",
                    "pattern": "(?i)(first)",
                },
                {
                    "rule_id": "dup-1",
                    "category": "prompt_injection",
                    "action": "MONITOR",
                    "severity": "LOW",
                    "pattern": "(?i)(second)",
                    "priority": 50,
                },
            ],
        })
        loader = FirewallRuleLoader(str(path))
        rules = loader.load()
        dup_ids = [r.rule_id for r in rules]
        assert dup_ids.count("dup-1") == 1
        winning = next(r for r in rules if r.rule_id == "dup-1")
        assert winning.category == DetectionCategory.PROMPT_INJECTION
        assert winning.action.value == "MONITOR"

    def test_get_rules_by_category(self, tmp_path: Path):
        path = _write_yaml(tmp_path / "by_category.yaml", {
            "version": "1.0",
            "rules": [
                {
                    "rule_id": "r1", "category": "jailbreak",
                    "action": "BLOCK", "severity": "HIGH", "pattern": "(?i)(x)",
                },
                {
                    "rule_id": "r2", "category": "jailbreak",
                    "action": "BLOCK", "severity": "HIGH", "pattern": "(?i)(y)",
                },
                {
                    "rule_id": "r3", "category": "prompt_injection",
                    "action": "BLOCK", "severity": "HIGH", "pattern": "(?i)(z)",
                },
            ],
        })
        loader = FirewallRuleLoader(str(path))
        loader.load()
        jailbreak_rules = loader.get_rules_by_category(DetectionCategory.JAILBREAK)
        assert len(jailbreak_rules) == 2
        assert all(r.category == DetectionCategory.JAILBREAK for r in jailbreak_rules)

    def test_category_config_loaded(self):
        loader = FirewallRuleLoader("config/prompt-security-rules.yaml")
        loader.load()
        config = loader.category_config
        assert len(config) == 7
        for cat_name in [c.value for c in DetectionCategory]:
            assert cat_name in config
            assert config[cat_name].enabled is True
            assert config[cat_name].threshold == 0.85

    def test_severity_mapping_loaded(self):
        loader = FirewallRuleLoader("config/prompt-security-rules.yaml")
        loader.load()
        mapping = loader.severity_mapping
        assert mapping.high.value == "BLOCK"
        assert mapping.medium.value == "FLAG_AND_FORWARD"
        assert mapping.low.value == "MONITOR"


class TestLoadFirewallRules:
    def test_module_level_function(self):
        rules = load_firewall_rules("config/prompt-security-rules.yaml")
        assert len(rules) >= 7

    def test_default_path(self):
        rules = load_firewall_rules()
        assert len(rules) >= 7
