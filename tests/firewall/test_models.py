from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from anonreq.firewall.models import (
    DetectionCategory,
    DetectionResult,
    FirewallAction,
    FirewallRule,
    RuleCategoryConfig,
    SeverityActionMapping,
    SeverityLevel,
)


class TestDetectionCategory:
    def test_has_all_seven_categories(self):
        assert len(DetectionCategory) == 7
        values = {c.value for c in DetectionCategory}
        assert values == {
            "prompt_injection",
            "jailbreak",
            "system_prompt_extraction",
            "instruction_override",
            "role_escalation",
            "hidden_tool_invocation",
            "secret_exfiltration",
        }

    @pytest.mark.parametrize(
        "member,expected",
        [
            (DetectionCategory.PROMPT_INJECTION, "prompt_injection"),
            (DetectionCategory.JAILBREAK, "jailbreak"),
            (DetectionCategory.SYSTEM_PROMPT_EXTRACTION, "system_prompt_extraction"),
            (DetectionCategory.INSTRUCTION_OVERRIDE, "instruction_override"),
            (DetectionCategory.ROLE_ESCALATION, "role_escalation"),
            (DetectionCategory.HIDDEN_TOOL_INVOCATION, "hidden_tool_invocation"),
            (DetectionCategory.SECRET_EXFILTRATION, "secret_exfiltration"),
        ],
    )
    def test_member_values(self, member: DetectionCategory, expected: str):
        assert member.value == expected


class TestSeverityLevel:
    def test_has_all_expected_values(self):
        assert SeverityLevel.LOW == "LOW"
        assert SeverityLevel.MEDIUM == "MEDIUM"
        assert SeverityLevel.HIGH == "HIGH"

    def test_contains_expected_members(self):
        values = {m.value for m in SeverityLevel}
        assert values == {"LOW", "MEDIUM", "HIGH"}


class TestFirewallAction:
    def test_has_all_expected_values(self):
        assert FirewallAction.BLOCK == "BLOCK"
        assert FirewallAction.FLAG_AND_FORWARD == "FLAG_AND_FORWARD"
        assert FirewallAction.MONITOR == "MONITOR"

    def test_contains_expected_members(self):
        values = {m.value for m in FirewallAction}
        assert values == {"BLOCK", "FLAG_AND_FORWARD", "MONITOR"}


class TestFirewallRule:
    def test_valid_minimal(self):
        rule = FirewallRule(rule_id="test-1", category=DetectionCategory.JAILBREAK)
        assert rule.rule_id == "test-1"
        assert rule.category == DetectionCategory.JAILBREAK
        assert rule.enabled is True
        assert rule.action == FirewallAction.BLOCK
        assert rule.severity == SeverityLevel.HIGH
        assert rule.priority == 0
        assert rule.pattern is None
        assert rule.semantic_description is None
        assert rule.metadata == {}

    def test_valid_with_pattern(self):
        rule = FirewallRule(
            rule_id="test-2",
            category=DetectionCategory.PROMPT_INJECTION,
            pattern=r"(?i)(ignore.*instructions)",
            action=FirewallAction.BLOCK,
            severity=SeverityLevel.HIGH,
            priority=100,
        )
        assert rule.rule_id == "test-2"
        assert rule.pattern == r"(?i)(ignore.*instructions)"
        assert rule.priority == 100

    def test_valid_with_semantic_description(self):
        rule = FirewallRule(
            rule_id="test-3",
            category=DetectionCategory.SYSTEM_PROMPT_EXTRACTION,
            semantic_description="Detect attempts to extract system prompt",
            action=FirewallAction.FLAG_AND_FORWARD,
            severity=SeverityLevel.MEDIUM,
        )
        assert rule.semantic_description == "Detect attempts to extract system prompt"
        assert rule.action == FirewallAction.FLAG_AND_FORWARD

    def test_valid_with_metadata(self):
        rule = FirewallRule(
            rule_id="test-4",
            category=DetectionCategory.SECRET_EXFILTRATION,
            metadata={"owner": "security", "source": "owasp"},
        )
        assert rule.metadata == {"owner": "security", "source": "owasp"}

    def test_rejects_unknown_category(self):
        with pytest.raises(ValidationError):
            FirewallRule(rule_id="test-5", category="unknown_category")

    def test_rejects_invalid_action(self):
        with pytest.raises(ValidationError):
            FirewallRule(
                rule_id="test-6",
                category=DetectionCategory.JAILBREAK,
                action="INVALID",
            )

    def test_rejects_invalid_severity(self):
        with pytest.raises(ValidationError):
            FirewallRule(
                rule_id="test-7",
                category=DetectionCategory.JAILBREAK,
                severity="CRITICAL",
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            FirewallRule(
                rule_id="test-8",
                category=DetectionCategory.JAILBREAK,
                unknown_field="bad",
            )


class TestDetectionResult:
    def test_valid_minimal(self):
        result = DetectionResult(
            category=DetectionCategory.JAILBREAK,
            confidence=0.95,
            severity=SeverityLevel.HIGH,
            action=FirewallAction.BLOCK,
        )
        assert result.category == DetectionCategory.JAILBREAK
        assert result.confidence == 0.95
        assert result.severity == SeverityLevel.HIGH
        assert result.action == FirewallAction.BLOCK
        assert result.rule_id is None
        assert result.matched_text_snippet is None

    def test_valid_full(self):
        result = DetectionResult(
            category=DetectionCategory.PROMPT_INJECTION,
            confidence=1.0,
            rule_id="direct_injection_001",
            severity=SeverityLevel.HIGH,
            action=FirewallAction.BLOCK,
            matched_text_snippet="ignore all previous instructions",
        )
        assert result.rule_id == "direct_injection_001"
        assert result.matched_text_snippet == "ignore all previous instructions"

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            DetectionResult(
                category=DetectionCategory.JAILBREAK,
                confidence=1.5,
                severity=SeverityLevel.HIGH,
                action=FirewallAction.BLOCK,
            )

    def test_confidence_can_be_zero(self):
        result = DetectionResult(
            category=DetectionCategory.JAILBREAK,
            confidence=0.0,
            severity=SeverityLevel.LOW,
            action=FirewallAction.MONITOR,
        )
        assert result.confidence == 0.0

    def test_confidence_can_be_one(self):
        result = DetectionResult(
            category=DetectionCategory.JAILBREAK,
            confidence=1.0,
            severity=SeverityLevel.HIGH,
            action=FirewallAction.BLOCK,
        )
        assert result.confidence == 1.0

    def test_negative_confidence_raises(self):
        with pytest.raises(ValidationError):
            DetectionResult(
                category=DetectionCategory.JAILBREAK,
                confidence=-0.1,
                severity=SeverityLevel.HIGH,
                action=FirewallAction.BLOCK,
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            DetectionResult(
                category=DetectionCategory.JAILBREAK,
                confidence=0.9,
                severity=SeverityLevel.HIGH,
                action=FirewallAction.BLOCK,
                extra="bad",
            )


class TestRuleCategoryConfig:
    def test_defaults(self):
        config = RuleCategoryConfig()
        assert config.enabled is True
        assert config.threshold == 0.85

    def test_valid_custom(self):
        config = RuleCategoryConfig(enabled=False, threshold=0.5)
        assert config.enabled is False
        assert config.threshold == 0.5

    def test_threshold_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            RuleCategoryConfig(threshold=1.5)

    def test_threshold_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            RuleCategoryConfig(threshold=-0.1)

    def test_threshold_zero_is_valid(self):
        config = RuleCategoryConfig(threshold=0.0)
        assert config.threshold == 0.0

    def test_threshold_one_is_valid(self):
        config = RuleCategoryConfig(threshold=1.0)
        assert config.threshold == 1.0

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            RuleCategoryConfig(enabled=True, threshold=0.9, extra="bad")


class TestSeverityActionMapping:
    def test_defaults(self):
        mapping = SeverityActionMapping()
        assert mapping.high == FirewallAction.BLOCK
        assert mapping.medium == FirewallAction.FLAG_AND_FORWARD
        assert mapping.low == FirewallAction.MONITOR

    def test_valid_custom(self):
        mapping = SeverityActionMapping(
            high=FirewallAction.FLAG_AND_FORWARD,
            medium=FirewallAction.MONITOR,
            low=FirewallAction.BLOCK,
        )
        assert mapping.high == FirewallAction.FLAG_AND_FORWARD
        assert mapping.medium == FirewallAction.MONITOR
        assert mapping.low == FirewallAction.BLOCK

    def test_rejects_invalid_action(self):
        with pytest.raises(ValidationError):
            SeverityActionMapping(high="INVALID")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            SeverityActionMapping(high=FirewallAction.BLOCK, extra="bad")
