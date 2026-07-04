"""Tests for context-word confidence boosting in the detection pipeline.

Per D-013:
- Context-word boosting: financial crime high-risk words within 50 chars
  of an entity → confidence +0.15 (capped at 1.0)
- Only financial crime entity types are boosted (IBAN, PAYMENT_REF,
  CUSTOMER_ID, AML_CASE_REF)
"""

from __future__ import annotations

import pytest

from anonreq.detection.boost import ContextBooster
from anonreq.models.detection import DetectionResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def booster() -> ContextBooster:
    return ContextBooster(config_path="config/financial_crime_words.yaml")


# ---------------------------------------------------------------------------
# Proximity detection tests
# ---------------------------------------------------------------------------


class TestProximityDetection:
    """Tests for is_within_proximity and find_high_risk_word_positions."""

    def test_entity_within_proximity_returns_true(self, booster: ContextBooster):
        """Entity at positions 10-20, word at 5-8, proximity 50 → True."""
        assert booster.is_within_proximity(10, 20, [(5, 8)], 50) is True

    def test_entity_beyond_proximity_returns_false(self, booster: ContextBooster):
        """Entity at 10-20, word at 100-105, proximity 50 → False."""
        assert booster.is_within_proximity(10, 20, [(100, 105)], 50) is False

    def test_word_before_entity_within_proximity(self, booster: ContextBooster):
        """Word 40 chars before entity start, proximity 50 → True."""
        assert booster.is_within_proximity(50, 60, [(10, 15)], 50) is True

    def test_word_after_entity_within_proximity(self, booster: ContextBooster):
        """Word 30 chars after entity end, proximity 50 → True."""
        assert booster.is_within_proximity(10, 20, [(40, 50)], 50) is True

    def test_word_exactly_at_proximity_boundary(self, booster: ContextBooster):
        """Word exactly 50 chars from entity start → True (boundary inclusive)."""
        assert booster.is_within_proximity(60, 70, [(10, 15)], 50) is True

    def test_word_beyond_proximity_boundary(self, booster: ContextBooster):
        """Word 51 chars from entity start → False (boundary exclusive)."""
        assert booster.is_within_proximity(61, 70, [(10, 15)], 50) is False

    def test_empty_word_positions(self, booster: ContextBooster):
        """No word positions → False."""
        assert booster.is_within_proximity(10, 20, [], 50) is False

    def test_find_high_risk_words_in_text(self, booster: ContextBooster):
        """find_high_risk_word_positions returns correct positions."""
        text = "processing swift transfer for payment"
        positions = booster.find_high_risk_word_positions(text, ["swift", "payment"])
        # "swift" is at index 11-15, "payment" is at index 24-30
        assert (11, 16) in positions
        assert (24, 31) in positions
        assert len(positions) == 2

    def test_find_high_risk_words_case_insensitive(self, booster: ContextBooster):
        """find_high_risk_word_positions is case-insensitive."""
        text = "SWIFT Transfer PAYMENT"
        positions = booster.find_high_risk_word_positions(text, ["swift", "payment"])
        assert len(positions) == 2

    def test_find_high_risk_words_no_match(self, booster: ContextBooster):
        """No high-risk words in text → empty list."""
        text = "hello world this is harmless"
        positions = booster.find_high_risk_word_positions(text, ["swift", "payment"])
        assert positions == []


# ---------------------------------------------------------------------------
# Boost application tests
# ---------------------------------------------------------------------------


class TestBoostApplication:
    """Tests for apply_boost and the boost pipeline."""

    def test_boost_within_proximity_increases_confidence(self, booster: ContextBooster):
        """Entity within 50 chars of high-risk word gets +0.15 boost."""
        entity = DetectionResult(
            entity_type="IBAN", start=20, end=30, score=0.7, source="regex"
        )
        text = "swift transfer payment IBAN12345 more text"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.85, rel=1e-9)

    def test_boost_beyond_proximity_no_change(self, booster: ContextBooster):
        """Entity beyond 50 chars of high-risk word → no boost."""
        entity = DetectionResult(
            entity_type="IBAN",
            start=100,
            end=110,
            score=0.7,
            source="regex",
        )
        # Word "swift" at position 5-9, entity at 100-110 → 90+ chars apart
        text = "swift" + "x" * 90 + "IBAN12345"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.7, rel=1e-9)

    def test_boost_capped_at_one_point_zero(self, booster: ContextBooster):
        """0.9 + 0.15 → 1.0 (capped)."""
        entity = DetectionResult(
            entity_type="IBAN", start=10, end=20, score=0.9, source="regex"
        )
        text = "swift transfer payment IBAN12345 more text"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == 1.0

    def test_boost_at_max_stays_max(self, booster: ContextBooster):
        """Confidence already at 1.0 stays at 1.0."""
        entity = DetectionResult(
            entity_type="IBAN", start=10, end=20, score=1.0, source="regex"
        )
        text = "swift transfer payment IBAN12345 more text"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == 1.0

    def test_multiple_words_no_stacking(self, booster: ContextBooster):
        """Multiple high-risk words near entity → single +0.15 boost."""
        entity = DetectionResult(
            entity_type="IBAN", start=30, end=40, score=0.5, source="regex"
        )
        # Multiple high-risk words near the entity
        text = "swift transfer payment IBAN12345 clearing swift"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.65, rel=1e-9)

    def test_only_financial_entity_types_boosted(self, booster: ContextBooster):
        """Only IBAN, PAYMENT_REF, CUSTOMER_ID, AML_CASE_REF are boosted."""
        # This entity is within proximity of high-risk words
        text = "swift transfer payment of important data"

        financial_entity = DetectionResult(
            entity_type="IBAN", start=35, end=40, score=0.5, source="regex"
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(financial_entity, text, word_positions)
        assert boosted.score == pytest.approx(0.65, rel=1e-9)

    def test_non_financial_entity_not_boosted(self, booster: ContextBooster):
        """Non-financial entity types (EMAIL, PERSON) are NOT boosted."""
        text = "swift transfer payment for processing"

        email_entity = DetectionResult(
            entity_type="EMAIL", start=35, end=45, score=0.7, source="regex"
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(email_entity, text, word_positions)
        assert boosted.score == pytest.approx(0.7, rel=1e-9)

    def test_payment_ref_entity_boosted(self, booster: ContextBooster):
        """PAYMENT_REF entity type is boosted."""
        entity = DetectionResult(
            entity_type="PAYMENT_REF", start=30, end=40, score=0.6, source="regex"
        )
        text = "swift transfer payment PAYREF001 clearing"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.75, rel=1e-9)

    def test_customer_id_entity_boosted(self, booster: ContextBooster):
        """CUSTOMER_ID entity type is boosted."""
        entity = DetectionResult(
            entity_type="CUSTOMER_ID", start=25, end=35, score=0.55, source="regex"
        )
        text = "swift transfer payment CUST001234 clearing"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.70, rel=1e-9)

    def test_aml_case_ref_entity_boosted(self, booster: ContextBooster):
        """AML_CASE_REF entity type is boosted."""
        entity = DetectionResult(
            entity_type="AML_CASE_REF", start=25, end=35, score=0.5, source="ner"
        )
        text = "aml compliance case AML2024001 review"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == pytest.approx(0.65, rel=1e-9)

    def test_boost_preserves_other_fields(self, booster: ContextBooster):
        """Boost preserves entity_type, start, end, and source fields."""
        entity = DetectionResult(
            entity_type="IBAN", start=10, end=20, score=0.7, source="regex"
        )
        text = "swift transfer payment IBAN12345 more text"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.entity_type == "IBAN"
        assert boosted.start == 10
        assert boosted.end == 20
        assert boosted.source == "regex"

    def test_load_config_with_custom_path(self, booster: ContextBooster):
        """Config is loaded from the specified path."""
        assert booster.boost_amount == 0.15
        assert booster.proximity == 50
        assert "IBAN" in booster.financial_entity_types
        assert "swift" in [w.lower() for w in booster.high_risk_words]

    def test_config_from_yaml_matches_expected_values(self, booster: ContextBooster):
        """Verify config values match the YAML specification."""
        cfg = booster.load_config()
        assert cfg["financial_crime"]["boost_amount"] == 0.15
        assert cfg["financial_crime"]["proximity_chars"] == 50
        assert "IBAN" in cfg["financial_crime"]["financial_entity_types"]
