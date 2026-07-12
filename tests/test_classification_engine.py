"""Tests for ClassificationEngine — deterministic max sensitivity algorithm.

Tests the 5-level classification hierarchy (Public→Highly Restricted)
and the deterministic max algorithm per CLASS-01, CLASS-02.
"""

from __future__ import annotations

import logging

from anonreq.models.classification import (
    ENTITY_CLASSIFICATION_MAP,
    ClassificationLevel,
)
from anonreq.services.classification_engine import ClassificationEngine

# ---------------------------------------------------------------------------
# ClassificationLevel enum tests
# ---------------------------------------------------------------------------


class TestClassificationLevel:
    def test_enum_values(self):
        assert ClassificationLevel.PUBLIC == 0
        assert ClassificationLevel.INTERNAL == 1
        assert ClassificationLevel.CONFIDENTIAL == 2
        assert ClassificationLevel.RESTRICTED == 3
        assert ClassificationLevel.HIGHLY_RESTRICTED == 4

    def test_enum_ordering(self):
        levels = list(ClassificationLevel)
        assert levels == [
            ClassificationLevel.PUBLIC,
            ClassificationLevel.INTERNAL,
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
            ClassificationLevel.HIGHLY_RESTRICTED,
        ]

    def test_max_operator(self):
        assert max([ClassificationLevel.INTERNAL, ClassificationLevel.CONFIDENTIAL]) == ClassificationLevel.CONFIDENTIAL  # noqa: E501
        assert max([ClassificationLevel.HIGHLY_RESTRICTED, ClassificationLevel.PUBLIC]) == ClassificationLevel.HIGHLY_RESTRICTED  # noqa: E501


# ---------------------------------------------------------------------------
# ENTITY_CLASSIFICATION_MAP tests
# ---------------------------------------------------------------------------


class TestEntityClassificationMap:
    def test_covers_all_phase_2_entity_types(self):
        assert len(ENTITY_CLASSIFICATION_MAP) >= 25

    def test_person_is_internal(self):
        assert ENTITY_CLASSIFICATION_MAP["PERSON"] == ClassificationLevel.INTERNAL

    def test_email_is_confidential(self):
        assert ENTITY_CLASSIFICATION_MAP["EMAIL"] == ClassificationLevel.CONFIDENTIAL

    def test_credit_card_is_restricted(self):
        assert ENTITY_CLASSIFICATION_MAP["CREDIT_CARD"] == ClassificationLevel.RESTRICTED

    def test_api_key_is_highly_restricted(self):
        assert ENTITY_CLASSIFICATION_MAP["API_KEY"] == ClassificationLevel.HIGHLY_RESTRICTED


# ---------------------------------------------------------------------------
# ClassificationEngine unit tests
# ---------------------------------------------------------------------------


class TestClassificationEngine:
    def make_engine(self) -> ClassificationEngine:
        return ClassificationEngine()

    # Test 1: Correct highest level for entity combinations
    async def test_email_and_person_returns_confidential(self):
        engine = self.make_engine()
        result = await engine.classify(["EMAIL", "PERSON"])
        assert result.highest == ClassificationLevel.CONFIDENTIAL

    async def test_api_key_and_source_code_returns_highly_restricted(self):
        engine = self.make_engine()
        result = await engine.classify(["API_KEY", "SOURCE_CODE"])
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED

    async def test_public_entity_does_not_raise(self):
        engine = self.make_engine()
        result = await engine.classify(["PERSON"])
        assert result.highest == ClassificationLevel.INTERNAL

    # Test 2: Undetected (empty entity list) defaults to Internal
    async def test_empty_entity_list_defaults_to_internal(self):
        engine = self.make_engine()
        result = await engine.classify([])
        assert result.highest == ClassificationLevel.INTERNAL
        assert result.labels == []
        assert result.detected_levels == []

    # Test 3: All labels preserved in result
    async def test_all_labels_preserved(self):
        engine = self.make_engine()
        result = await engine.classify(["PERSON", "EMAIL", "IBAN"])
        assert result.labels == ["PERSON", "EMAIL", "IBAN"]
        assert result.detected_levels == [
            ClassificationLevel.INTERNAL,
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
        ]

    # Test 4: Deterministic — same input always same output
    async def test_deterministic_same_input_same_output(self):
        engine = self.make_engine()
        inputs = ["PERSON", "EMAIL", "PHONE", "IBAN"]
        first = await engine.classify(inputs)
        for _ in range(100):
            result = await engine.classify(inputs)
            assert result.highest == first.highest
            assert result.labels == first.labels
            assert result.detected_levels == first.detected_levels

    # Test 5: Individual entity mappings
    async def test_person_is_internal(self):
        engine = self.make_engine()
        result = await engine.classify(["PERSON"])
        assert result.highest == ClassificationLevel.INTERNAL

    async def test_email_is_confidential(self):
        engine = self.make_engine()
        result = await engine.classify(["EMAIL"])
        assert result.highest == ClassificationLevel.CONFIDENTIAL

    async def test_iban_is_restricted(self):
        engine = self.make_engine()
        result = await engine.classify(["IBAN"])
        assert result.highest == ClassificationLevel.RESTRICTED

    async def test_source_code_is_highly_restricted(self):
        engine = self.make_engine()
        result = await engine.classify(["SOURCE_CODE"])
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED

    # Test 6: Multiple entities — max wins
    async def test_multiple_entities_max_wins(self):
        engine = self.make_engine()
        result = await engine.classify(["PERSON", "EMAIL"])
        assert result.highest == ClassificationLevel.CONFIDENTIAL
        result2 = await engine.classify(["PERSON", "CREDIT_CARD"])
        assert result2.highest == ClassificationLevel.RESTRICTED
        result3 = await engine.classify(["PERSON", "EMAIL", "API_KEY"])
        assert result3.highest == ClassificationLevel.HIGHLY_RESTRICTED

    # Test 7: Unknown entity type defaults to Internal with log warning
    async def test_unknown_entity_defaults_to_internal(self, caplog):
        engine = self.make_engine()
        with caplog.at_level(logging.WARNING):
            result = await engine.classify(["UNKNOWN_TYPE"])
        assert result.highest == ClassificationLevel.INTERNAL
        assert result.labels == ["UNKNOWN_TYPE"]
        assert result.detected_levels == [ClassificationLevel.INTERNAL]
        assert any("UNKNOWN_TYPE" in record.message for record in caplog.records)

    async def test_unknown_entity_defaults_to_internal_mixed(self, caplog):
        engine = self.make_engine()
        with caplog.at_level(logging.WARNING):
            result = await engine.classify(["PERSON", "MYSTERY_ENTITY", "EMAIL"])
        assert result.highest == ClassificationLevel.CONFIDENTIAL
        assert "MYSTERY_ENTITY" in result.labels
        assert any("MYSTERY_ENTITY" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Client override tests
# ---------------------------------------------------------------------------


class TestClientOverride:
    def make_engine(self) -> ClassificationEngine:
        return ClassificationEngine()

    async def test_no_override_returns_detected(self):
        engine = self.make_engine()
        result = await engine.classify_with_client_override(["PERSON"])
        assert result.highest == ClassificationLevel.INTERNAL
        assert result.client_override is False
        assert result.client_asserted_level is None

    async def test_client_override_increases_level(self):
        engine = self.make_engine()
        result = await engine.classify_with_client_override(
            ["PERSON"], client_level=ClassificationLevel.HIGHLY_RESTRICTED,
        )
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
        assert result.client_override is True
        assert result.client_asserted_level == ClassificationLevel.HIGHLY_RESTRICTED

    async def test_client_override_lower_ignored(self):
        engine = self.make_engine()
        result = await engine.classify_with_client_override(
            ["API_KEY"], client_level=ClassificationLevel.INTERNAL,
        )
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
        assert result.client_override is False
        assert result.client_asserted_level is None

    async def test_client_override_equal_ignored(self):
        engine = self.make_engine()
        result = await engine.classify_with_client_override(
            ["API_KEY"], client_level=ClassificationLevel.HIGHLY_RESTRICTED,
        )
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
        assert result.client_override is False
        assert result.client_asserted_level is None


# ---------------------------------------------------------------------------
# Entity map override tests
# ---------------------------------------------------------------------------


class TestEntityMapOverride:
    async def test_custom_entity_map_constructor(self):
        custom_map = {"PERSON": ClassificationLevel.HIGHLY_RESTRICTED}
        engine = ClassificationEngine(entity_map=custom_map)
        result = await engine.classify(["PERSON"])
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED

    async def test_update_entity_map_merges(self):
        engine = ClassificationEngine()
        engine.update_entity_map({"PERSON": ClassificationLevel.CONFIDENTIAL})
        result = await engine.classify(["PERSON"])
        assert result.highest == ClassificationLevel.CONFIDENTIAL

    async def test_update_entity_map_does_not_remove_existing(self):
        engine = ClassificationEngine()
        engine.update_entity_map({"NEW_TYPE": ClassificationLevel.RESTRICTED})
        result = await engine.classify(["NEW_TYPE"])
        assert result.highest == ClassificationLevel.RESTRICTED
        result2 = await engine.classify(["EMAIL"])
        assert result2.highest == ClassificationLevel.CONFIDENTIAL


# ---------------------------------------------------------------------------
# ClassificationService tests — header parsing + per-level handling (Plan 12-02)
# ---------------------------------------------------------------------------


class TestClassificationService:
    """ClassificationService wraps engine with client header parsing and per-level handling policy."""  # noqa: E501

    async def test_parse_client_header_returns_level(self):
        from anonreq.services.classification import ClassificationService
        assert ClassificationService.parse_client_header("CONFIDENTIAL") == ClassificationLevel.CONFIDENTIAL  # noqa: E501
        assert ClassificationService.parse_client_header("HIGHLY_RESTRICTED") == ClassificationLevel.HIGHLY_RESTRICTED  # noqa: E501
        assert ClassificationService.parse_client_header("internal") == ClassificationLevel.INTERNAL

    async def test_parse_client_header_none_on_empty(self):
        from anonreq.services.classification import ClassificationService
        assert ClassificationService.parse_client_header(None) is None
        assert ClassificationService.parse_client_header("") is None

    async def test_parse_client_header_none_on_invalid(self):
        from anonreq.services.classification import ClassificationService
        assert ClassificationService.parse_client_header("INVALID_LEVEL") is None
        assert ClassificationService.parse_client_header("TOP_SECRET") is None

    async def test_classify_no_override_returns_detected(self):
        from anonreq.services.classification import ClassificationService
        svc = ClassificationService()
        result = await svc.classify(["PERSON"])
        assert result.highest == ClassificationLevel.INTERNAL
        assert result.client_override is False

    async def test_classify_with_client_override_increases(self):
        from anonreq.services.classification import ClassificationService
        svc = ClassificationService()
        result = await svc.classify(["PERSON"], client_level=ClassificationLevel.HIGHLY_RESTRICTED)
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
        assert result.client_override is True

    async def test_classify_client_lower_ignored(self):
        from anonreq.services.classification import ClassificationService
        svc = ClassificationService()
        result = await svc.classify(["API_KEY"], client_level=ClassificationLevel.INTERNAL)
        assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
        assert result.client_override is False

    # Per-level handling policy tests

    async def test_handling_public_is_allow_and_anonymize(self):
        from anonreq.services.classification import ClassificationService
        result = await ClassificationService().classify([])
        assert result.handling_action == "allow_and_anonymize"

    async def test_handling_internal_is_allow_and_anonymize(self):
        from anonreq.services.classification import ClassificationService
        result = await ClassificationService().classify(["PERSON"])
        assert result.handling_action == "allow_and_anonymize"

    async def test_handling_confidential_is_allow_and_anonymize(self):
        from anonreq.services.classification import ClassificationService
        result = await ClassificationService().classify(["EMAIL"])
        assert result.handling_action == "allow_and_anonymize"

    async def test_handling_restricted_is_anonymize_and_flag(self):
        from anonreq.services.classification import ClassificationService
        result = await ClassificationService().classify(["CREDIT_CARD"])
        assert result.handling_action == "anonymize_and_flag"

    async def test_handling_highly_restricted_is_block(self):
        from anonreq.services.classification import ClassificationService
        result = await ClassificationService().classify(["API_KEY"])
        assert result.handling_action == "block"


# ---------------------------------------------------------------------------
# Configuration loading tests (Task 2 — entity mapping YAML)
# ---------------------------------------------------------------------------


class TestClassificationConfig:
    """Validate entity mapping configuration from ``config/classification.yaml``.

    Tests ensure the YAML-based entity mapping matches the Python defaults
    and that override merging works as expected for Phase 8 policy YAML.
    """

    def test_default_yaml_entity_mapping_has_all_types(self) -> None:
        """Default YAML mapping covers all 28 Phase 2 entity types."""
        import yaml

        with open("config/classification.yaml") as f:
            cfg = yaml.safe_load(f)
        mapping = cfg["classification"]["entity_mapping"]
        assert len(mapping) >= 25
        assert mapping["PERSON"] == "INTERNAL"
        assert mapping["EMAIL"] == "CONFIDENTIAL"
        assert mapping["CREDIT_CARD"] == "RESTRICTED"
        assert mapping["API_KEY"] == "HIGHLY_RESTRICTED"

    def test_default_yaml_matches_python_default_enum(self) -> None:
        """YAML mappings correspond to correct ClassificationLevel values."""
        import yaml

        with open("config/classification.yaml") as f:
            cfg = yaml.safe_load(f)
        mapping = cfg["classification"]["entity_mapping"]
        for entity, level_str in mapping.items():
            expected = ClassificationLevel[level_str]
            assert ENTITY_CLASSIFICATION_MAP[entity] == expected, (
                f"Mismatch for {entity}: YAML says {level_str}, "
                f"Python says {ENTITY_CLASSIFICATION_MAP[entity].name}"
            )

    def test_yaml_loads_with_2024_presidio_entity_types(self) -> None:
        """All Phase 2 entity types are present in the YAML mapping."""
        import yaml

        with open("config/classification.yaml") as f:
            cfg = yaml.safe_load(f)
        mapping = cfg["classification"]["entity_mapping"]

        phase2_entities = [
            "PERSON", "EMAIL", "PHONE", "CREDIT_CARD", "CREDIT_CARD_TYPE",
            "IBAN", "IP_ADDRESS", "LOCATION", "DATE_TIME", "NRP",
            "URL", "DOMAIN_NAME", "SWIFT", "BANK_ACCOUNT", "SSN",
            "MEDICAL_LICENSE", "DRIVERS_LICENSE", "PASSPORT", "TAX_ID",
            "CRYPTO", "API_KEY", "PASSWORD", "AUTH_TOKEN", "SOURCE_CODE",
            "HEALTH_INFO", "ORGANIZATION", "AGE", "ZIP_CODE",
        ]
        for entity in phase2_entities:
            assert entity in mapping, f"Missing {entity} in YAML mapping"

    def test_yaml_level_display_names_configured(self) -> None:
        """Each classification level has a display_name."""
        import yaml

        with open("config/classification.yaml") as f:
            cfg = yaml.safe_load(f)
        levels = cfg["classification"]["levels"]
        for level in ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "HIGHLY_RESTRICTED"):
            assert level in levels, f"Missing level {level}"
            assert "display_name" in levels[level], f"Missing display_name for {level}"
            assert "ordinal" in levels[level], f"Missing ordinal for {level}"

    def test_override_merges_with_defaults(self) -> None:
        """Overrides from tenant policy YAML merge correctly."""
        import asyncio

        engine = ClassificationEngine()
        # Simulate Phase 8 tenant override loading
        overrides = {"SSN": ClassificationLevel.HIGHLY_RESTRICTED}
        engine.update_entity_map(overrides)

        async def _run():
            # Override takes effect
            result = await engine.classify(["SSN"])
            assert result.highest == ClassificationLevel.HIGHLY_RESTRICTED
            # Defaults preserved
            result2 = await engine.classify(["EMAIL"])
            assert result2.highest == ClassificationLevel.CONFIDENTIAL

        asyncio.run(_run())
