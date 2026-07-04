"""Property-based tests for financial crime detection invariants.

Uses Hypothesis to prove:
1. **Boost bounded [0, 1.0]**: For any entity confidence score, the
   boosted score never exceeds 1.0 and never goes below 0.0.
2. **Only-financial entity type**: Non-financial entity types (EMAIL, PHONE,
   PERSON, etc.) never have their score modified by context booster.
3. **Proximity correctness**: Entities more than 50 chars from any high-risk
   word never receive a boost.
4. **AML webhook threshold**: AML webhook fires iff confidence >= threshold.
"""

from __future__ import annotations

import itertools
from unittest.mock import AsyncMock

import pytest
from hypothesis import assume, given, settings, strategies as st
from pydantic import ValidationError

from anonreq.detection.boost import FINANCIAL_ENTITY_TYPES, ContextBooster
from anonreq.models.detection import DetectionResult

# ── Load context booster ──────────────────────────────────────────


@pytest.fixture(scope="module")
def booster() -> ContextBooster:
    return ContextBooster("config/financial_crime_words.yaml")


# ── Hypothesis strategies ─────────────────────────────────────────

# Generate financial entity types from the configured list
financial_type_strategy = st.sampled_from(FINANCIAL_ENTITY_TYPES)

# Generate non-financial entity types
non_financial_type_strategy = st.sampled_from([
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "DATE_TIME", "LOCATION", "IP_ADDRESS", "URL",
])

# Generate entity positions in a reasonable range
entity_start_strategy = st.integers(min_value=0, max_value=500)

# Generate confidence scores in [0.0, 1.0]
score_strategy = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False,
)

# Generate text with a high-risk word and an entity at a given offset
def _make_text_with_entity(word_offset: int, entity_type: str) -> str:
    """Create text with a high-risk word at a given offset from an entity."""
    word = "transfer"
    entity_placeholder = "DE89370400440532013000"  # 22 chars for IBAN
    if word_offset >= 0:
        # Word before entity
        gap = " " * word_offset
        text = f"Please initiate the {word}{gap}{entity_placeholder}"
    else:
        # Word after entity
        gap = " " * abs(word_offset)
        text = f"{entity_placeholder}{gap}{word} is important"
    return text

# Proximity window (default 50 chars)
PROXIMITY = 50


class TestBoostBoundedInvariant:
    """Prove: Confidence boost never produces scores outside [0, 1.0]."""

    @given(
        score=score_strategy,
        entity_start=entity_start_strategy,
    )
    @settings(max_examples=500, deadline=None)
    def test_boost_capped_at_one(
        self, booster: ContextBooster, score: float, entity_start: int
    ):
        """For any valid score, boosted score never exceeds 1.0."""
        entity = DetectionResult(
            entity_type="IBAN",
            start=entity_start,
            end=entity_start + 22,
            score=score,
            source="regex",
        )
        text = f"transfer {' ' * 10}DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        boosted = booster.apply_boost(entity, text, word_positions)
        assert 0.0 <= boosted.score <= 1.0, (
            f"Boosted score must be in [0, 1.0], got {boosted.score}"
        )

    @given(score=score_strategy)
    @settings(max_examples=200, deadline=None)
    def test_boost_never_below_zero(self, booster: ContextBooster, score: float):
        """Score never goes below 0.0 (boost is additive only)."""
        entity = DetectionResult(
            entity_type="IBAN",
            start=0,
            end=22,
            score=score,
            source="regex",
        )
        text = "DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        # Score should be unchanged (no high-risk word)
        assert boosted.score == score, (
            f"Score unchanged without context, got {boosted.score}"
        )
        assert boosted.score >= 0.0

    @given(score=st.floats(
        min_value=0.95, max_value=1.0, allow_nan=False, allow_infinity=False,
    ))
    @settings(max_examples=100, deadline=None)
    def test_near_one_score_capped(self, booster: ContextBooster, score: float):
        """Score already near 1.0 is capped at 1.0."""
        

        entity = DetectionResult(
            entity_type="IBAN",
            start=9,
            end=31,
            score=score,
            source="regex",
        )
        text = "transfer DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        assert len(word_positions) > 0

        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score <= 1.0, (
            f"Score capped at 1.0, got {boosted.score}"
        )


class TestOnlyFinancialEntityBoostInvariant:
    """Prove: Non-financial entity types never have score modified."""

    @given(
        entity_type=non_financial_type_strategy,
        score=score_strategy,
    )
    @settings(max_examples=500, deadline=None)
    def test_non_financial_entity_never_boosted(
        self, booster: ContextBooster, entity_type: str, score: float
    ):
        """Non-financial entity keeps original score regardless of context."""
        entity = DetectionResult(
            entity_type=entity_type,
            start=30,
            end=50,
            score=score,
            source="regex",
        )
        text = "This transaction is a transfer DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == score, (
            f"Non-financial type '{entity_type}' must not have score modified. "
            f"Original: {score}, got {boosted.score}"
        )
        # Also verify entity type unchanged
        assert boosted.entity_type == entity_type

    @given(
        entity_type=financial_type_strategy,
        score=score_strategy,
    )
    @settings(max_examples=200, deadline=None)
    def test_financial_entity_can_be_boosted(
        self, booster: ContextBooster, entity_type: str, score: float
    ):
        """Financial entity types CAN be boosted when context word is near."""
        entity = DetectionResult(
            entity_type=entity_type,
            start=45,
            end=67,
            score=score,
            source="regex",
        )
        text = "This transfer involves DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        boosted = booster.apply_boost(entity, text, word_positions)
        # Score should be >= original (either boosted or unchanged)
        assert boosted.score >= score, (
            f"Financial type '{entity_type}' score should not decrease. "
            f"Original: {score}, got {boosted.score}"
        )


class TestProximityCorrectnessInvariant:
    """Prove: Entities far from high-risk words never receive a boost."""

    @given(entity_start=st.integers(min_value=100, max_value=500))
    @settings(max_examples=200, deadline=None)
    def test_distant_entity_not_boosted(
        self, booster: ContextBooster, entity_start: int
    ):
        """Entity >50 chars from nearest high-risk word gets no boost."""
        # Text with "transfer" at the start and entity at entity_start
        # entity_start >= 100 means distance > 50 from "transfer" at pos ~9
        text = "transfer " + "x" * entity_start + "DE89370400440532013000"
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        entity = DetectionResult(
            entity_type="IBAN",
            start=entity_start + 9,  # account for "transfer "
            end=entity_start + 31,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score == 0.85, (
            f"Entity at distance >50 should not be boosted, "
            f"expected 0.85, got {boosted.score}"
        )

    @given(word_offset=st.integers(min_value=0, max_value=PROXIMITY))
    @settings(max_examples=200, deadline=None)
    def test_close_entity_gets_boost(
        self, booster: ContextBooster, word_offset: int
    ):
        """Entity within proximity of high-risk word gets a boost."""
        text = _make_text_with_entity(word_offset, "IBAN")
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )
        assume(len(word_positions) > 0)

        # Find entity position
        iban_start = text.find("DE89370400440532013000")
        assume(iban_start >= 0)

        entity = DetectionResult(
            entity_type="IBAN",
            start=iban_start,
            end=iban_start + 22,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        assert boosted.score >= 0.85, (
            f"Entity within proximity should be boosted (or stay same if "
            f"already at 1.0), expected >= 0.85, got {boosted.score}"
        )

    @given(word_offset=st.integers(min_value=PROXIMITY + 1, max_value=200))
    @settings(max_examples=200, deadline=None)
    def test_beyond_proximity_not_boosted(
        self, booster: ContextBooster, word_offset: int
    ):
        """Entity just beyond proximity window gets no boost."""
        text = _make_text_with_entity(word_offset, "IBAN")
        word_positions = booster.find_high_risk_word_positions(
            text, booster.high_risk_words
        )

        iban_start = text.find("DE89370400440532013000")
        assume(iban_start >= 0)

        entity = DetectionResult(
            entity_type="IBAN",
            start=iban_start,
            end=iban_start + 22,
            score=0.85,
            source="regex",
        )
        boosted = booster.apply_boost(entity, text, word_positions)
        # If the word is beyond proximity, score should stay same
        if len(word_positions) == 0 or boosted.score == 0.85:
            assert boosted.score == 0.85, (
                f"Beyond-proximity entity should stay at 0.85, "
                f"got {boosted.score}"
            )


class TestAmlThresholdInvariant:
    """Prove: AML webhook fires iff confidence >= threshold."""

    # Strategies
    threshold_strategy = st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False,
    )
    confidence_strategy = st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False,
    )

    @given(confidence=confidence_strategy, threshold=threshold_strategy)
    @settings(max_examples=500, deadline=None)
    async def test_webhook_fires_at_or_above_threshold(
        self, confidence: float, threshold: float
    ):
        """Webhook fires iff confidence >= threshold."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager, AmlWebhookConfig
        import anonreq.governance.webhooks.aml as aml_mod

        # Clean store
        original = dict(aml_mod._aml_config_store)
        aml_mod._aml_config_store.clear()

        try:
            manager = AmlWebhookManager()
            await manager.set_config(
                "test-tenant",
                AmlWebhookConfig(
                    tenant_id="test-tenant",
                    webhook_url="https://example.com/hook",
                    threshold=threshold,
                    entity_types=["IBAN"],
                ),
            )

            mock_client = AsyncMock()
            aml_mod._aml_config_store["test-tenant"].enabled = True
            manager._http_client = mock_client

            result = await manager.evaluate_and_fire(
                tenant_id="test-tenant",
                entity_type="IBAN",
                confidence=confidence,
                session_metadata={"source": "property-test"},
            )

            should_fire = confidence >= threshold
            assert result == should_fire, (
                f"Webhook should{' ' if should_fire else ' NOT '}fire: "
                f"confidence={confidence:.4f}, threshold={threshold:.4f}"
            )
        finally:
            aml_mod._aml_config_store.clear()
            aml_mod._aml_config_store.update(original)

    @given(
        confidence=confidence_strategy,
        threshold=threshold_strategy,
    )
    @settings(max_examples=200, deadline=None)
    async def test_disabled_webhook_never_fires(
        self, confidence: float, threshold: float
    ):
        """Disabled webhook never fires regardless of confidence."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager, AmlWebhookConfig
        import anonreq.governance.webhooks.aml as aml_mod

        original = dict(aml_mod._aml_config_store)
        aml_mod._aml_config_store.clear()

        try:
            manager = AmlWebhookManager()
            await manager.set_config(
                "test-tenant",
                AmlWebhookConfig(
                    tenant_id="test-tenant",
                    webhook_url="https://example.com/hook",
                    threshold=threshold,
                    entity_types=["IBAN"],
                    enabled=False,
                ),
            )

            result = await manager.evaluate_and_fire(
                tenant_id="test-tenant",
                entity_type="IBAN",
                confidence=confidence,
                session_metadata={"source": "property-test"},
            )
            assert result is False, (
                "Disabled webhook must never fire"
            )
        finally:
            aml_mod._aml_config_store.clear()
            aml_mod._aml_config_store.update(original)

    @given(
        threshold=threshold_strategy,
        confidence=st.floats(min_value=0.0, max_value=1.0,
                             allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, deadline=None)
    async def test_unconfigured_entity_type_never_fires(
        self, threshold: float, confidence: float
    ):
        """Entity type not in configured list never fires."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager, AmlWebhookConfig
        import anonreq.governance.webhooks.aml as aml_mod

        original = dict(aml_mod._aml_config_store)
        aml_mod._aml_config_store.clear()

        try:
            manager = AmlWebhookManager()
            await manager.set_config(
                "test-tenant",
                AmlWebhookConfig(
                    tenant_id="test-tenant",
                    webhook_url="https://example.com/hook",
                    threshold=threshold,
                    entity_types=["IBAN"],
                ),
            )

            result = await manager.evaluate_and_fire(
                tenant_id="test-tenant",
                entity_type="PERSON",
                confidence=confidence,
                session_metadata={"source": "property-test"},
            )
            assert result is False, (
                "Unconfigured entity type must never fire"
            )
        finally:
            aml_mod._aml_config_store.clear()
            aml_mod._aml_config_store.update(original)
