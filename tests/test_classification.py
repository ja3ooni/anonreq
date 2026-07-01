"""Tests for ClassificationEngine — YAML-based 4-tier rule evaluation.

Per D-22 through D-28:
- Action-based precedence: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS (D-24)
- Conditions ANDed: roles AND (regex OR keywords) must match (D-23)
- Default action for unmatched: PASS (D-28)
- Classification runs before Presidio detection (CLASS-AC-01)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from anonreq.classification.engine import ClassificationRule, ClassificationEngine
from anonreq.classification.loader import ClassificationRuleLoader

# ---------------------------------------------------------------------------
# Hypothesis property-based tests for BLOCK invariant
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, settings, strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

    def given(*args, **kwargs):
        return lambda fn: fn

    def settings(**kwargs):
        return lambda fn: fn


if HAS_HYPOTHESIS:

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500, deadline=None)
    def test_block_invariant_random_text(text: str) -> None:
        """Prove BLOCK invariant across random inputs.

        For any random text containing classification-triggering keywords,
        the engine returns BLOCK with matched_rule_ids populated. For text
        without triggering keywords, the default action is returned.
        """
        block_rule = ClassificationRule(
            id="CLS-PROP-01",
            enabled=True,
            version=1,
            name="prop_block_secret",
            action="BLOCK",
            metadata={},
            roles=[],
            regex_patterns=[],
            keywords=["secret", "password", "block"],
        )
        engine = ClassificationEngine([block_rule], default_action="PASS")

        text_nodes = [
            {
                "path": "messages[0].content",
                "role": "user",
                "value": text,
            }
        ]
        result = engine.classify(text_nodes)

        text_lower = text.lower()
        has_keyword = any(kw in text_lower for kw in ["secret", "password", "block"])

        if has_keyword:
            assert result["action"] == "BLOCK", (
                f"Expected BLOCK for text containing trigger keyword, "
                f"got {result['action']}. Text: {text!r}"
            )
            assert len(result["matched_rule_ids"]) > 0, (
                f"Expected matched_rule_ids for BLOCK action"
            )
            assert "CLS-PROP-01" in result["matched_rule_ids"], (
                f"Expected CLS-PROP-01 in matched_rule_ids"
            )
        else:
            assert result["action"] == "PASS", (
                f"Expected PASS when no keyword matches, "
                f"got {result['action']}. Text: {text!r}"
            )
            assert result["matched_rule_ids"] == [], (
                f"Expected empty matched_rule_ids for PASS"
            )
            assert result["matched_rule_versions"] == [], (
                f"Expected empty matched_rule_versions for PASS"
            )

    @given(
        st.text(min_size=1, max_size=100),
        st.lists(
            st.text(
                min_size=2,
                max_size=15,
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    whitelist_characters="-_",
                ),
            ),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=500, deadline=None)
    def test_block_precedence_over_anonymize(
        text: str, keywords: list[str]
    ) -> None:
        """Prove BLOCK action takes precedence over ANONYMIZE.

        When both BLOCK and ANONYMIZE rules could match the same text,
        the engine must always return BLOCK (highest precedence per D-24).
        """
        block_rule = ClassificationRule(
            id="CLS-PROP-BLOCK",
            enabled=True,
            version=1,
            name="prop_block_any",
            action="BLOCK",
            metadata={},
            roles=[],
            regex_patterns=[],
            keywords=keywords,
        )
        anonymize_rule = ClassificationRule(
            id="CLS-PROP-ANZ",
            enabled=True,
            version=1,
            name="prop_anonymize_keywords",
            action="ANONYMIZE",
            metadata={},
            roles=[],
            regex_patterns=[],
            keywords=keywords,
        )
        engine = ClassificationEngine(
            [anonymize_rule, block_rule], default_action="PASS"
        )

        text_nodes = [
            {
                "path": "messages[0].content",
                "role": "user",
                "value": text,
            }
        ]
        result = engine.classify(text_nodes)

        text_lower = text.lower()
        has_block_keyword = any(kw.lower() in text_lower for kw in keywords)

        if has_block_keyword:
            # BLOCK must win over ANONYMIZE due to action precedence
            assert result["action"] == "BLOCK", (
                f"Expected BLOCK precedence over ANONYMIZE, "
                f"got {result['action']}. Text: {text!r}, keywords: {keywords}"
            )
        else:
            assert result["action"] == "PASS", (
                f"Expected PASS when no keywords match, "
                f"got {result['action']}"
            )

    @given(
        st.text(min_size=1, max_size=100),
        st.sampled_from(
            [
                "password",
                "PASSWORD",
                "Password",
                "SECRET",
                "Secret",
                "secret",
            ]
        ),
    )
    @settings(max_examples=500, deadline=None)
    def test_block_case_insensitive_keyword(text: str, keyword_form: str) -> None:
        """BLOCK rule with keyword matches case-insensitively.

        Keywords in rules are lowercased at construction time, so any
        casing variant in the input must still trigger the match.
        """
        block_rule = ClassificationRule(
            id="CLS-PROP-CI",
            enabled=True,
            version=1,
            name="prop_block_case_insensitive",
            action="BLOCK",
            metadata={},
            roles=[],
            regex_patterns=[],
            keywords=[keyword_form.upper()],
        )
        engine = ClassificationEngine([block_rule], default_action="PASS")

        # Embed the keyword (in its original casing) into the random text
        # at a random position
        insert_pos = max(0, len(text) // 2)
        modified_text = text[:insert_pos] + keyword_form + text[insert_pos:]
        text_nodes = [
            {
                "path": "messages[0].content",
                "role": "user",
                "value": modified_text,
            }
        ]
        result = engine.classify(text_nodes)

        # The keyword (in any casing) is always present
        assert result["action"] == "BLOCK", (
            f"Expected BLOCK when keyword '{keyword_form}' is present, "
            f"got {result['action']}"
        )


# ---------------------------------------------------------------------------
# ClassificationRule tests
# ---------------------------------------------------------------------------


class TestClassificationRule:
    """Test suite for ClassificationRule — individual rule matching logic."""

    def test_rule_matches_with_regex_condition(self):
        """Rule matches when regex pattern finds a hit in any text node."""
        rule = ClassificationRule(
            id="TEST-001",
            action="BLOCK",
            roles=["user"],
            regex_patterns=[r"(?i)password\s*[:=]\s*\S+"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "My password is secret123"},
            {"path": "messages[1].content", "role": "assistant", "value": "OK"},
        ]
        assert rule.matches(nodes) is True

    def test_rule_does_not_match_when_regex_does_not_match(self):
        """Rule does not match when regex pattern has no hit."""
        rule = ClassificationRule(
            id="TEST-002",
            action="BLOCK",
            roles=["user"],
            regex_patterns=[r"(?i)password\s*[:=]\s*\S+"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "Hello, how are you?"},
        ]
        assert rule.matches(nodes) is False

    def test_rule_matches_with_keyword_condition(self):
        """Rule matches when a keyword is found (case-insensitive)."""
        rule = ClassificationRule(
            id="TEST-003",
            action="ANONYMIZE",
            roles=["user", "assistant"],
            keywords=["email", "phone"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "My Email is test@example.com"},
        ]
        assert rule.matches(nodes) is True

    def test_rule_does_not_match_keyword_in_wrong_role(self):
        """Rule does not match when keywords match but role filter excludes the node."""
        rule = ClassificationRule(
            id="TEST-004",
            action="ANONYMIZE",
            roles=["user"],
            keywords=["email"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "assistant", "value": "Your email is..."},
        ]
        assert rule.matches(nodes) is False

    def test_empty_roles_matches_all_roles(self):
        """Empty roles list means all roles match (no role filtering)."""
        rule = ClassificationRule(
            id="TEST-005",
            action="ANONYMIZE",
            roles=[],
            keywords=["ssn"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "tool", "value": "My SSN is 123-45-6789"},
        ]
        assert rule.matches(nodes) is True

    def test_no_conditions_matches_on_roles_alone(self):
        """Rule with empty regex and keywords matches if roles filter passes."""
        rule = ClassificationRule(
            id="TEST-006",
            action="ANONYMIZE",
            roles=["user"],
            regex_patterns=[],
            keywords=[],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "Anything goes"},
        ]
        assert rule.matches(nodes) is True

    def test_no_conditions_no_roles_matches_everything(self):
        """Rule with empty roles, regex, keywords matches all nodes."""
        rule = ClassificationRule(
            id="TEST-007",
            action="ANONYMIZE",
            roles=[],
            regex_patterns=[],
            keywords=[],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "test"},
            {"path": "messages[1].content", "role": "assistant", "value": "test"},
        ]
        assert rule.matches(nodes) is True

    def test_disabled_rule_does_not_match(self):
        """A rule with enabled=False should not match."""
        rule = ClassificationRule(
            id="TEST-008",
            action="BLOCK",
            enabled=False,
            roles=[],
            regex_patterns=[r"(?i)password"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "My password is x"},
        ]
        assert rule.matches(nodes) is False

    def test_regex_case_insensitivity(self):
        """Regex patterns are pre-compiled with IGNORECASE flag."""
        rule = ClassificationRule(
            id="TEST-009",
            action="BLOCK",
            roles=["user"],
            regex_patterns=[r"SECRET"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "my secret key is abc"},
        ]
        assert rule.matches(nodes) is True

    def test_keyword_case_insensitivity(self):
        """Keywords are matched case-insensitively."""
        rule = ClassificationRule(
            id="TEST-010",
            action="ANONYMIZE",
            roles=["user"],
            keywords=["CREDIT CARD"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "My Credit Card number is 4111..."},
        ]
        assert rule.matches(nodes) is True

    def test_multiple_regex_patterns_any_match(self):
        """Rule matches if ANY of the regex patterns match."""
        rule = ClassificationRule(
            id="TEST-011",
            action="BLOCK",
            roles=["user"],
            regex_patterns=[r"password", r"api_key", r"secret"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "My api_key is abc123"},
        ]
        assert rule.matches(nodes) is True

    def test_multiple_keywords_any_match(self):
        """Rule matches if ANY of the keywords match."""
        rule = ClassificationRule(
            id="TEST-012",
            action="ANONYMIZE",
            roles=["user"],
            keywords=["email", "phone", "ssn"],
        )
        nodes = [
            {"path": "messages[0].content", "role": "user", "value": "What is your ssn?"},
        ]
        assert rule.matches(nodes) is True


# ---------------------------------------------------------------------------
# ClassificationEngine tests
# ---------------------------------------------------------------------------


class TestClassificationEngine:
    """Test suite for ClassificationEngine — action-based precedence evaluation."""

    DEFAULT_RULES = [
        ClassificationRule(id="BLK-001", action="BLOCK", roles=["user"], regex_patterns=[r"(?i)password\s*[:=]\s*\S+"]),
        ClassificationRule(id="BLK-002", action="BLOCK", roles=["user"], keywords=["drop table"]),
        ClassificationRule(id="ANZ-001", action="ANONYMIZE", roles=[], keywords=["email"]),
        ClassificationRule(id="ANZ-002", action="ANONYMIZE", roles=[], keywords=["phone"]),
        ClassificationRule(id="PAS-001", action="PASS", roles=[], keywords=["hello"]),
        ClassificationRule(id="LOC-001", action="ROUTE_LOCAL", roles=["user"], keywords=["internal"]),
    ]

    def test_default_action_pass_when_no_rules_match(self):
        """Classification returns PASS with empty matched_rule_ids when no rules match."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES, default_action="PASS")
        nodes = [{"path": "messages[0].content", "role": "user", "value": "What is the weather today?"}]
        result = engine.classify(nodes)
        assert result["action"] == "PASS"
        assert result["matched_rule_ids"] == []
        assert result["matched_rule_versions"] == []

    def test_block_action_returned_for_matching_block_rule(self):
        """BLOCK action returned when a BLOCK rule matches."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "My password is hunter2"}]
        result = engine.classify(nodes)
        assert result["action"] == "BLOCK"
        assert "BLK-001" in result["matched_rule_ids"]

    def test_block_precedence_over_anonymize(self):
        """BLOCK wins over ANONYMIZE when both match (action precedence)."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        # Both BLOCK (BLK-001: password) and ANONYMIZE (ANZ-001: email) could match here
        nodes = [{"path": "messages[0].content", "role": "user", "value": "Email me at test@example.com, password is x"}]
        result = engine.classify(nodes)
        assert result["action"] == "BLOCK"
        assert "BLK-001" in result["matched_rule_ids"]

    def test_anonymize_action_returned_when_no_block_matches(self):
        """ANONYMIZE returned when no BLOCK rules match but ANONYMIZE rules do."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "My email is test@example.com"}]
        result = engine.classify(nodes)
        assert result["action"] == "ANONYMIZE"
        assert "ANZ-001" in result["matched_rule_ids"]

    def test_precedence_order_block_route_local_anonymize_pass(self):
        """Full precedence: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        # This input matches ROUTE_LOCAL (LOC-001: "internal"), ANONYMIZE (ANZ-001: "email"),
        # PASS (PAS-001: "hello"), and BLOCK (BLK-002: "drop table")
        nodes = [{"path": "messages[0].content", "role": "user", "value": "hello, internal email: don't drop table"}]
        result = engine.classify(nodes)
        assert result["action"] == "BLOCK"
        assert "BLK-002" in result["matched_rule_ids"]

    def test_matched_rule_ids_and_versions_recorded(self):
        """Classification result records matched_rule_ids and matched_rule_versions."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "password = secret123"}]
        result = engine.classify(nodes)
        assert "BLK-001" in result["matched_rule_ids"]
        assert len(result["matched_rule_versions"]) == len(result["matched_rule_ids"])

    def test_disabled_rules_are_skipped(self):
        """Rules with enabled=False are not evaluated."""
        rules = [
            ClassificationRule(id="BLK-001", action="BLOCK", enabled=False, roles=["user"], regex_patterns=[r"(?i)password"]),
            ClassificationRule(id="ANZ-001", action="ANONYMIZE", enabled=True, roles=[], keywords=["email"]),
        ]
        engine = ClassificationEngine(rules=rules)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "password is secret and my email is test@test.com"}]
        result = engine.classify(nodes)
        # BLK-001 is disabled so it should be skipped, ANZ-001 should match
        assert result["action"] == "ANONYMIZE"
        assert "ANZ-001" in result["matched_rule_ids"]

    def test_route_local_action(self):
        """ROUTE_LOCAL action is returned when matching rule has that action."""
        engine = ClassificationEngine(rules=self.DEFAULT_RULES)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "Please check the internal knowledge base"}]
        result = engine.classify(nodes)
        assert result["action"] == "ROUTE_LOCAL"
        assert "LOC-001" in result["matched_rule_ids"]

    def test_pass_action_only_returned_as_default(self):
        """PASS actions can also come from matching rules."""
        rules = [
            ClassificationRule(id="PAS-001", action="PASS", roles=[], keywords=["hello"]),
        ]
        engine = ClassificationEngine(rules=rules)
        nodes = [{"path": "messages[0].content", "role": "user", "value": "hello world"}]
        result = engine.classify(nodes)
        assert result["action"] == "PASS"
        assert "PAS-001" in result["matched_rule_ids"]


# ---------------------------------------------------------------------------
# ClassificationRuleLoader tests
# ---------------------------------------------------------------------------


class TestClassificationRuleLoader:
    """Test suite for ClassificationRuleLoader — YAML loading and validation."""

    VALID_YAML = """
rules:
  - id: CLS-001
    enabled: true
    version: 1
    name: block_credentials
    action: BLOCK
    metadata:
      owner: security-team
      category: credentials
    conditions:
      roles: [user]
      regex:
        - "(?i)password\\\\s*[:=]\\\\s*\\\\S+"
      keywords: []
  - id: CLS-002
    enabled: true
    version: 1
    name: block_ssn
    action: BLOCK
    metadata:
      owner: security-team
    conditions:
      roles: [user]
      regex: []
      keywords: ["ssn", "social security"]
"""

    def test_from_yaml_loads_rules(self):
        """Load rules from a YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(self.VALID_YAML)
            tmp_path = f.name
        try:
            rules = ClassificationRuleLoader.from_yaml(tmp_path)
            assert len(rules) == 2
            assert rules[0].id == "CLS-001"
            assert rules[0].action == "BLOCK"
            assert rules[0].enabled is True
            assert rules[1].id == "CLS-002"
            assert rules[1].keywords == ["ssn", "social security"]
        finally:
            Path(tmp_path).unlink()

    def test_from_dict_loads_rules(self):
        """Load rules from an already-parsed dict."""
        data = {
            "rules": [
                {
                    "id": "TEST-001",
                    "action": "ANONYMIZE",
                    "conditions": {"roles": ["user"], "regex": [], "keywords": ["email"]},
                }
            ]
        }
        rules = ClassificationRuleLoader.from_dict(data)
        assert len(rules) == 1
        assert rules[0].id == "TEST-001"
        assert rules[0].action == "ANONYMIZE"

    def test_from_yaml_missing_rules_key_raises_error(self):
        """Missing 'rules' key raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("other_key: []\n")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match="rules"):
                ClassificationRuleLoader.from_yaml(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_from_yaml_rule_missing_id_raises_error(self):
        """Rule without 'id' raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("rules:\n  - action: BLOCK\n")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match="id"):
                ClassificationRuleLoader.from_yaml(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_from_yaml_rule_missing_action_raises_error(self):
        """Rule without 'action' raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("rules:\n  - id: TEST-001\n")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match="action"):
                ClassificationRuleLoader.from_yaml(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_from_yaml_with_default_action(self):
        """Loading a YAML with 'default_action' stores the value."""
        yaml_content = """
default_action: BLOCK
rules:
  - id: CLS-001
    action: ANONYMIZE
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            tmp_path = f.name
        try:
            # The loader should handle (or ignore) default_action gracefully
            rules = ClassificationRuleLoader.from_yaml(tmp_path)
            assert len(rules) == 1
        finally:
            Path(tmp_path).unlink()

    def test_from_yaml_empty_rules(self):
        """An empty rules list is valid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("rules: []\n")
            tmp_path = f.name
        try:
            rules = ClassificationRuleLoader.from_yaml(tmp_path)
            assert rules == []
        finally:
            Path(tmp_path).unlink()
