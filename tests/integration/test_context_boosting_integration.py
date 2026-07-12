"""Context boosting integration tests.

Covers:
- Financial crime words (transfer, payment, swift, settlement, etc.)
  within proximity of IBAN entities trigger confidence boost
- Boost NOT applied without high-risk word proximity
- Only financial entity types (IBAN, PAYMENT_REF, CUSTOMER_ID, AML_CASE_REF)
  are boosted — PERSON, EMAIL_ADDRESS are NOT
- Boost capped at 1.0
- Multiple high-risk words produce a SINGLE +0.15 boost (not stacked)
"""

from __future__ import annotations

import pytest

from anonreq.detection.boost import (
    FINANCIAL_ENTITY_TYPES,
    ContextBooster,
)
from anonreq.models.detection import DetectionResult


@pytest.fixture
def booster() -> ContextBooster:
    """Return a ContextBooster using the live config file."""
    return ContextBooster("config/financial_crime_words.yaml")


# ── Basic entity detection for tests ──────────────────────────────

_DETECT_IBAN = DetectionResult(
    entity_type="IBAN",
    start=80,
    end=102,
    score=0.85,
    source="regex",
)
_DETECT_EMAIL = DetectionResult(
    entity_type="EMAIL_ADDRESS",
    start=110,
    end=130,
    score=0.95,
    source="regex",
)
_DETECT_PHONE = DetectionResult(
    entity_type="PHONE_NUMBER",
    start=140,
    end=155,
    score=0.80,
    source="regex",
)


# ── Boost applied ─────────────────────────────────────────────────


class TestBoostApplied:
    """Verify confidence boosted when financial crime word near entity."""

    def test_transfer_word_boosts_iban(self, booster: ContextBooster):
        """'transfer' within 50 chars of IBAN produces +0.15 boost."""
        text = (
            "Please initiate the transfer for account "
            "DE89370400440532013000. This is urgent."
        )
        # "transfer" ends at index 29, IBAN starts at index 45 → distance=16
        iban = DetectionResult(
            entity_type="IBAN",
            start=45,
            end=67,
            score=0.85,
            source="regex",
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        assert len(word_positions) > 0

        boosted = booster.apply_boost(iban, text, word_positions)
        assert boosted.score == pytest.approx(1.0, abs=0.01), \
            f"IBAN should be boosted from 0.85+0.15=1.0, got {boosted.score}"

    def test_payment_word_boosts_iban(self, booster: ContextBooster):
        """'payment' within proximity boosts IBAN confidence."""
        text = (
            "The payment was processed for "
            "DE89370400440532013000 yesterday."
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        iban = DetectionResult(
            entity_type="IBAN",
            start=37,
            end=59,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(iban, text, word_positions)
        assert boosted.score == pytest.approx(1.0, abs=0.01), \
            f"IBAN should be boosted, got {boosted.score}"

    def test_swift_word_boosts_iban(self, booster: ContextBooster):
        """'swift' within proximity boosts IBAN confidence."""
        text = (
            "SWIFT transfer details: "
            "DE89370400440532013000"
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        iban = DetectionResult(
            entity_type="IBAN",
            start=23,
            end=45,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(iban, text, word_positions)
        assert boosted.score == pytest.approx(1.0, abs=0.01), \
            f"IBAN should be boosted, got {boosted.score}"


# ── No boost without high-risk word ───────────────────────────────


class TestNoBoostWithoutContext:
    """Verify no boost applied when no high-risk word is near the entity."""

    def test_no_boost_without_high_risk_word(self, booster: ContextBooster):
        """IBAN without any financial crime keywords nearby keeps base score."""
        text = "DE89370400440532013000 is my account number."
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        assert len(word_positions) == 0, "No high-risk words in plain text"

        boosted = booster.apply_boost(_DETECT_IBAN, text, word_positions)
        assert boosted.score == 0.85, \
            f"Without context words, score should stay at 0.85, got {boosted.score}"

    def test_no_boost_when_word_too_far(self, booster: ContextBooster):
        """High-risk word outside proximity window does not boost."""
        text = (
            "transfer" + " " * 60 +
            "DE89370400440532013000"
        )
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        assert len(word_positions) > 0

        iban = DetectionResult(
            entity_type="IBAN",
            start=65,
            end=87,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(iban, text, word_positions)
        assert boosted.score == 0.85, \
            "Word > 50 chars away should not boost"


# ── Type filtering ────────────────────────────────────────────────


class TestOnlyFinancialTypesBoosted:
    """Verify only financial entity types receive the boost."""

    def test_person_not_boosted_by_financial_word(self, booster: ContextBooster):
        """PERSON entity type should NOT be boosted by financial context."""
        text = "The transfer was arranged by John Doe yesterday."
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        person = DetectionResult(
            entity_type="PERSON",
            start=30,
            end=38,
            score=0.90,
            source="spacy",
        )
        boosted = booster.apply_boost(person, text, word_positions)
        assert boosted.score == 0.90, \
            "PERSON should not be boosted by financial context"

    def test_email_not_boosted(self, booster: ContextBooster):
        """EMAIL_ADDRESS is not in financial entity types and is not boosted."""
        text = "Send the transfer receipt to user@example.com"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(_DETECT_EMAIL, text, word_positions)
        assert boosted.score == 0.95, \
            "EMAIL_ADDRESS should not be boosted by financial context"


# ── Financial entity types config ─────────────────────────────────


class TestFinancialEntityTypes:
    """Verify the configured financial entity types set."""

    def test_iban_is_financial_type(self):
        """IBAN must be in the financial entity types."""
        assert "IBAN" in FINANCIAL_ENTITY_TYPES

    def test_payment_ref_is_financial_type(self):
        """PAYMENT_REF must be in the financial entity types."""
        assert "PAYMENT_REF" in FINANCIAL_ENTITY_TYPES

    def test_customer_id_is_financial_type(self):
        """CUSTOMER_ID must be in the financial entity types."""
        assert "CUSTOMER_ID" in FINANCIAL_ENTITY_TYPES

    def test_aml_case_ref_is_financial_type(self):
        """AML_CASE_REF must be in the financial entity types."""
        assert "AML_CASE_REF" in FINANCIAL_ENTITY_TYPES


# ── Boost cap ─────────────────────────────────────────────────────


class TestBoostCap:
    """Verify boost is capped at 1.0."""

    def test_boost_capped_at_one(self, booster: ContextBooster):
        """Confidence reaching 1.0 stays 1.0."""
        text = "transfer DE89370400440532013000 payment swift settlement"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        iban = DetectionResult(
            entity_type="IBAN",
            start=9,
            end=31,
            score=0.95,  # Already high
            source="regex",
        )
        boosted = booster.apply_boost(iban, text, word_positions)
        assert boosted.score <= 1.0, \
            f"Boost must not exceed 1.0, got {boosted.score}"
        assert boosted.score == 1.0, \
            f"0.95 + 0.15 should cap at 1.0, got {boosted.score}"
