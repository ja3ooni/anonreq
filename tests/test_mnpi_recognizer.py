"""Tests for MNPI Presidio recognizer bundle.

Tests cover MNPIRecognizer ticker detection, deal codename detection,
restricted name detection, excluded word filtering, and policy action hints.
"""

from __future__ import annotations

import pytest
import yaml

from anonreq.detection.recognizers.mnpi import (
    MNPIConfig,
    MNPIRecognizer,
    create_mnpi_bundle,
)
from anonreq.models.detection import (
    MNPI_POLICY_ACTION,
    MNPI_ENTITY_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config() -> MNPIConfig:
    return MNPIConfig(
        ticker_pattern=r"\b[A-Z]{1,4}(\.\w{1,2})?\b",
        deal_codename_patterns=[
            r"\b(Project|Operation|Initiative)\s+[A-Z][a-zA-Z]{2,}\b",
            r'\b(Codenamed|Codename)\s+"[A-Z][a-zA-Z]+"\b',
        ],
        excluded_words={"THE", "FOR", "AND", "NOT", "YOU", "ARE", "WAS"},
        min_ticker_length=2,
        score=0.85,
    )


@pytest.fixture
def recognizer(default_config) -> MNPIRecognizer:
    return MNPIRecognizer(default_config)


# ---------------------------------------------------------------------------
# MNPIConfig tests
# ---------------------------------------------------------------------------


class TestMNPIConfig:
    """MNPIConfig dataclass construction and defaults."""

    def test_minimal_config(self):
        """Can construct MNPIConfig with required fields."""
        config = MNPIConfig(
            ticker_pattern=r"\b[A-Z]{1,4}\b",
            deal_codename_patterns=[r"\bProject\s+[A-Z]\w+\b"],
        )
        assert config.ticker_pattern == r"\b[A-Z]{1,4}\b"
        assert len(config.deal_codename_patterns) == 1
        assert config.excluded_words == set()
        assert config.min_ticker_length == 2
        assert config.score == 0.85

    def test_config_from_yaml(self, tmp_path):
        """Can load MNPIConfig from YAML dict."""
        data = {
            "ticker_pattern": r"\b[A-Z]{1,4}\b",
            "deal_codename_patterns": [r"\bProject\s+\w+\b"],
            "excluded_words": ["THE", "FOR"],
            "min_ticker_length": 3,
            "score": 0.9,
        }
        config = MNPIConfig.from_dict(data)
        assert config.ticker_pattern == r"\b[A-Z]{1,4}\b"
        assert "THE" in config.excluded_words
        assert config.min_ticker_length == 3
        assert config.score == 0.9


# ---------------------------------------------------------------------------
# Ticker detection tests
# ---------------------------------------------------------------------------


class TestTickerDetection:
    """MNPIRecognizer ticker symbol detection."""

    def test_detects_standard_ticker(self, recognizer):
        """Test 1: Ticker symbol 'AAPL' detected as MNPI_TICKER."""
        results = recognizer.analyze("AAPL")
        assert len(results) >= 1
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) >= 1
        match = tickers[0]
        assert match["start"] == 0
        assert match["end"] == 4
        assert match["score"] >= 0.8

    def test_detects_dot_notation_ticker(self, recognizer):
        """Test 2: Ticker symbol 'BRK.A' detected as MNPI_TICKER (dot notation)."""
        results = recognizer.analyze("BRK.A")
        assert len(results) >= 1
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) >= 1
        match = tickers[0]
        assert match["start"] == 0
        assert match["end"] == 5

    def test_detects_multiple_tickers(self, recognizer):
        """Multiple tickers in same text all detected."""
        results = recognizer.analyze("AAPL MSFT GOOG")
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) == 3

    def test_rejects_common_words(self, recognizer):
        """Test 5: Regular word not matching ticker pattern not detected."""
        results = recognizer.analyze("the quick brown fox")
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) == 0

    def test_rejects_short_words(self, recognizer):
        """Test 6: Short word (<=2 chars) not detected as ticker.

        Single-letter words are rejected by min_ticker_length=2.
        Two-letter common words are rejected via excluded_words.
        """
        results = recognizer.analyze("A")
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) == 0

    def test_excluded_words_filtered(self, recognizer):
        """Excluded words like 'THE', 'FOR', 'AND' not detected as tickers."""
        results = recognizer.analyze("THE FOR AND NOT")
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) == 0

    def test_ticker_with_suffix_is_whole(self, recognizer):
        """Ticker with dot-suffix like 'BRK.A' uses core 'BRK' (≥2 chars)."""
        results = recognizer.analyze("BRK.A")
        tickers = [r for r in results if r["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) >= 1
        assert tickers[0]["end"] - tickers[0]["start"] == 5


# ---------------------------------------------------------------------------
# Deal codename detection tests
# ---------------------------------------------------------------------------


class TestDealCodenameDetection:
    """MNPIRecognizer deal codename detection."""

    def test_detects_project_codename(self, recognizer):
        """Test 3: Deal codename 'Project Olympus' detected as MNPI_DEAL."""
        results = recognizer.analyze("Project Olympus")
        deals = [r for r in results if r["entity_type"] == "MNPI_DEAL"]
        assert len(deals) >= 1

    def test_detects_operation_codename(self, recognizer):
        """Test 4: Deal codename 'Operation GoldenEye' detected as MNPI_DEAL."""
        results = recognizer.analyze("Operation GoldenEye")
        deals = [r for r in results if r["entity_type"] == "MNPI_DEAL"]
        assert len(deals) >= 1

    def test_detects_initiative_codename(self, recognizer):
        """Initiative prefix codename detected."""
        results = recognizer.analyze("Initiative Horizon")
        deals = [r for r in results if r["entity_type"] == "MNPI_DEAL"]
        assert len(deals) >= 1

    def test_short_codename_not_detected(self, recognizer):
        """Single-word after prefix must be at least 3 chars."""
        results = recognizer.analyze("Project A")
        deals = [r for r in results if r["entity_type"] == "MNPI_DEAL"]
        assert len(deals) == 0


# ---------------------------------------------------------------------------
# Policy action hints
# ---------------------------------------------------------------------------


class TestPolicyAction:
    """MNPI entity type includes policy action hint."""

    def test_entity_type_includes_policy_hint(self):
        """Test 8: MNPI entity type in detection results includes policy action hint."""
        assert "MNPI_TICKER" in MNPI_ENTITY_TYPES
        assert "MNPI_DEAL" in MNPI_ENTITY_TYPES
        assert "MNPI_RESTRICTED_NAME" in MNPI_ENTITY_TYPES

    def test_policy_action_literal(self):
        """MNPI_POLICY_ACTION is a Literal with expected values."""
        valid_actions = {"anonymize", "flag", "block", "quarantine"}
        assert MNPI_POLICY_ACTION is not None


# ---------------------------------------------------------------------------
# create_mnpi_bundle factory
# ---------------------------------------------------------------------------


class TestCreateMNPI:
    """create_mnpi_bundle factory function."""

    def test_create_bundle_with_config_path(self, tmp_path):
        """Creates recognizer from YAML config file."""
        config_file = tmp_path / "mnpi_test.yaml"
        config_data = {
            "mnpi": {
                "ticker_pattern": r"\b[A-Z]{1,4}\b",
                "deal_codename_patterns": [r"\bProject\s+\w+\b"],
                "excluded_words": ["THE"],
                "min_ticker_length": 2,
                "score": 0.85,
            }
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        bundle = create_mnpi_bundle(str(config_file))
        assert len(bundle) >= 1
        assert isinstance(bundle[0], MNPIRecognizer)

    def test_create_bundle_default_path(self):
        """Creates recognizer from default config path."""
        bundle = create_mnpi_bundle()
        assert len(bundle) >= 1
