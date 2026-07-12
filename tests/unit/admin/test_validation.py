"""Config validation tests — valid/invalid YAML, bad regex, edge cases.

Covers:
- Validation rejects malformed regex patterns with descriptive error
- Validation rejects invalid match_type
- Validation passes on empty config
- Validation passes on well-formed config
"""

from __future__ import annotations

from anonreq.admin.config import (
    AtomicConfigRegistry,
    CustomRecognizerRule,
    ExclusionEntry,
    RulesConfig,
)


class TestConfigValidation:
    """AtomicConfigRegistry validation logic."""

    def test_validates_good_regex(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(
                    id="email-regex",
                    entity_type="EMAIL",
                    patterns=[r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
                ),
            ],
            exclusion_list=[],
        )
        success, error = registry.validate_and_swap(config)
        assert success is True
        assert error is None

    def test_rejects_unclosed_bracket(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(
                    id="bad-regex",
                    entity_type="X",
                    patterns=[r"[unclosed"],
                ),
            ],
            exclusion_list=[],
        )
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert error is not None
        assert "unterminated" in error or "bad" in error or "invalid" in error
        assert "recognizer[0].patterns[0]" in error

    def test_rejects_invalid_escape_sequence(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(
                    id="bad-escape",
                    entity_type="X",
                    patterns=[r"\xZZZ"],
                ),
            ],
            exclusion_list=[],
        )
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert error is not None

    def test_rejects_invalid_match_type(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[],
            exclusion_list=[
                ExclusionEntry(value="test", match_type="regex"),
            ],
        )
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert error is not None
        assert "match_type" in error.lower()
        assert "exclusion_list[0]" in error

    def test_accepts_valid_match_types(self):
        registry = AtomicConfigRegistry()
        for match_type in ("exact", "wildcard"):
            config = RulesConfig(
                custom_recognizers=[],
                exclusion_list=[
                    ExclusionEntry(value="test", match_type=match_type),
                ],
            )
            success, _error = registry.validate_and_swap(config)
            assert success is True, f"match_type '{match_type}' should be valid"

    def test_empty_config_passes(self):
        registry = AtomicConfigRegistry()
        empty = RulesConfig(custom_recognizers=[], exclusion_list=[])
        success, error = registry.validate_and_swap(empty)
        assert success is True
        assert error is None

    def test_multiple_recognizers_all_valid(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(id="r1", entity_type="TYPE_1", patterns=[r"\d{3}-\d{2}-\d{4}"]),  # noqa: E501
                CustomRecognizerRule(id="r2", entity_type="TYPE_2", patterns=[r"\w+@\w+\.\w+"]),
                CustomRecognizerRule(id="r3", entity_type="TYPE_3", patterns=[r"\d{5}"]),
            ],
            exclusion_list=[],
        )
        success, error = registry.validate_and_swap(config)
        assert success is True
        assert error is None

    def test_identifies_which_pattern_fails(self):
        registry = AtomicConfigRegistry()
        config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(id="good", entity_type="G", patterns=[r"valid"]),
                CustomRecognizerRule(id="bad", entity_type="B", patterns=[r"[invalid"]),
            ],
            exclusion_list=[],
        )
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert "recognizer[1]" in error
