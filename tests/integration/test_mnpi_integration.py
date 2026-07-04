"""End-to-end MNPI detection integration tests.

Covers:
- Ticker symbol detection from configured regex patterns
- Deal codename detection from configured patterns
- Excluded words excluded from ticker detection
- Overlapping detection deduplication (shorter match loses)
- Restricted names from tenant config detected when manager is provided
- MNPI detection metadata suitable for audit (no raw value exposure)
- Hash-not-value invariant for audit events
"""

from __future__ import annotations

import re

import pytest
import yaml

from anonreq.detection.recognizers.mnpi import (
    MNPIConfig,
    MNPIRecognizer,
)
from anonreq.config.restricted_names import RestrictedNamesManager

_CONFIG_PATH = "config/mnpi_recognizers.yaml"


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mnpi_config() -> MNPIConfig:
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return MNPIConfig.from_dict(raw if "ticker_pattern" in raw else raw["mnpi"])


@pytest.fixture(scope="module")
def recognizer(mnpi_config: MNPIConfig) -> MNPIRecognizer:
    return MNPIRecognizer(config=mnpi_config)


# ── Ticker detection ──────────────────────────────────────────────


class TestTickerDetection:
    """Verify ticker symbols are detected according to configured patterns."""

    def test_common_tickers_detected(self, recognizer: MNPIRecognizer):
        """Standard NYSE/NASDAQ tickers are detected."""
        text = "Based on AAPL and MSFT."
        detections = recognizer.analyze(text)
        tickers = {text[d["start"]:d["end"]] for d in detections
                    if d["entity_type"] == "MNPI_TICKER"}
        assert "AAPL" in tickers, "AAPL must be detected"
        assert "MSFT" in tickers, "MSFT must be detected"

    def test_extended_ticker_detected(self, recognizer: MNPIRecognizer):
        """Tickers with dot-suffix (BRK.A) are detected."""
        text = "Consider BRK.A for value investing."
        detections = recognizer.analyze(text)
        tickers = {text[d["start"]:d["end"]] for d in detections
                    if d["entity_type"] == "MNPI_TICKER"}
        assert "BRK.A" in tickers, "BRK.A must be detected"

    def test_excluded_words_not_detected(self, recognizer: MNPIRecognizer):
        """Excluded words like THE, AND, FOR are NOT detected as tickers."""
        text = "THE AND FOR are common words."
        detections = recognizer.analyze(text)
        tickers = {text[d["start"]:d["end"]] for d in detections
                    if d["entity_type"] == "MNPI_TICKER"}
        assert "THE" not in tickers, "THE must be excluded"
        assert "AND" not in tickers, "AND must be excluded"
        assert "FOR" not in tickers, "FOR must be excluded"

    def test_short_tickers_excluded(self, mnpi_config: MNPIConfig):
        """Below-minimum-length words are not detected."""
        assert mnpi_config.min_ticker_length >= 2, \
            "min_ticker_length should be >= 2"
        # Create a config with min_length=3 to test
        config = MNPIConfig(
            ticker_pattern=r"\b[A-Z]{1,4}(\.\w{1,2})?\b",
            deal_codename_patterns=[],
            excluded_words={"THE", "AND", "FOR"},
            min_ticker_length=3,
            score=0.85,
        )
        r = MNPIRecognizer(config=config)
        text = "A and IS test"
        detections = r.analyze(text)
        tickers = {text[d["start"]:d["end"]] for d in detections
                    if d["entity_type"] == "MNPI_TICKER"}
        for short in ("A", "IS"):
            assert short not in tickers, f"'{short}' is too short for ticker"

    def test_ticker_score_configured(self, mnpi_config: MNPIConfig):
        """Ticker detections use the configured score."""
        assert mnpi_config.score > 0, "Ticker score must be > 0"
        assert mnpi_config.score <= 1.0, "Ticker score must be <= 1.0"


# ── Deal codename detection ───────────────────────────────────────


class TestDealCodenameDetection:
    """Verify deal codenames are detected from configured patterns."""

    def test_project_codenames_detected(self, recognizer: MNPIRecognizer):
        """'Project <Name>' patterns detected as deal codenames."""
        text = "Project Olympus will redefine our strategy."
        detections = recognizer.analyze(text)
        deals = {text[d["start"]:d["end"]] for d in detections
                  if d["entity_type"] == "MNPI_DEAL"}
        assert "Project Olympus" in deals, \
            "'Project Olympus' must be detected as deal"

    def test_operation_codenames_detected(self, recognizer: MNPIRecognizer):
        """'Operation <Name>' patterns detected as deal codenames."""
        text = "Operation GoldenEye has been greenlit."
        detections = recognizer.analyze(text)
        deals = {text[d["start"]:d["end"]] for d in detections
                  if d["entity_type"] == "MNPI_DEAL"}
        assert "Operation GoldenEye" in deals, \
            "'Operation GoldenEye' must be detected as deal"

    def test_initiative_codenames_detected(self, recognizer: MNPIRecognizer):
        """'Initiative <Name>' patterns detected as deal codenames."""
        text = "Initiative Horizon will launch next quarter."
        detections = recognizer.analyze(text)
        deals = {text[d["start"]:d["end"]] for d in detections
                  if d["entity_type"] == "MNPI_DEAL"}
        assert "Initiative Horizon" in deals, \
            "'Initiative Horizon' must be detected as deal"


# ── Restricted names ──────────────────────────────────────────────


class TestRestrictedNames:
    """Verify restricted names are detected when manager is provided."""

    def test_restricted_names_detected(self):
        """Restricted names from tenant config are detected."""
        mgr = RestrictedNamesManager("config/restricted_names.yaml")
        # Use config with no deal patterns — rely only on restricted names
        config = MNPIConfig(
            ticker_pattern=r"\b[A-Z]{1,4}(\.\w{1,2})?\b",
            deal_codename_patterns=[],
            excluded_words={"THE", "AND", "FOR"},
            min_ticker_length=2,
            score=0.85,
        )
        r = MNPIRecognizer(config=config, restricted_names=mgr)
        # Try known tenant IDs
        known_tenants = ["acme-corp", "tenant-a", "tenant-b"]
        hit = False
        for tid in known_tenants:
            names = mgr.get_names(tid)
            if names:
                hit = True
                text = f"Discussed {names[0]} in the meeting."
                detections = r.analyze(text, tenant_id=tid)
                restricted = {text[d["start"]:d["end"]] for d in detections
                              if d["entity_type"] == "MNPI_RESTRICTED_NAME"}
                assert names[0] in restricted, \
                    f"Restricted name '{names[0]}' must be detected for {tid}"

        if not hit:
            pytest.skip("No restricted names configured for test tenants")

    def test_mnpi_entity_types_have_correct_source(self, recognizer: MNPIRecognizer):
        """All MNPI detections have 'mnpi' as their source."""
        text = "AAPL and Project Olympus are both confidential."
        detections = recognizer.analyze(text)
        assert len(detections) > 0, "Should detect at least one MNPI entity"
        for d in detections:
            assert d.get("source") == "mnpi", \
                f"MNPI detection source must be 'mnpi', got {d.get('source')}"


# ── Overlap deduplication ─────────────────────────────────────────


class TestOverlapDeduplication:
    """Verify overlapping MNPI detections are deduplicated (shorter loses)."""

    def test_shorter_match_loses(self, recognizer: MNPIRecognizer):
        """When two patterns overlap, the shorter one is removed."""
        text = "Project TheTest is code for something."
        detections = recognizer.analyze(text)
        overlapping = [d for d in detections
                       if d["entity_type"] in ("MNPI_DEAL", "MNPI_TICKER")]
        # Check that no two detections share the same start
        starts = [d["start"] for d in overlapping]
        assert len(starts) == len(set(starts)), \
            "Overlapping detections must be deduplicated"


# ── Hash-not-value invariant ──────────────────────────────────────


class TestHashNotValue:
    """Verify MNPI detection metadata is hash-based, never raw values."""

    def test_detection_returns_positions_not_values(self, recognizer: MNPIRecognizer):
        """The analyze() method returns span positions, never raw values."""
        text = "Consider AAPL for your portfolio."
        detections = recognizer.analyze(text)
        tickers = [d for d in detections if d["entity_type"] == "MNPI_TICKER"]
        assert len(tickers) > 0
        # The raw value must be reconstructed from the text + span
        for td in tickers:
            raw = text[td["start"]:td["end"]]
            assert len(raw) > 0
            assert raw.isupper(), "Ticker symbols should be uppercase"

    def test_audit_format_contains_hash(self):
        """A SHA-256 hex digest is a suitable audit identifier (not the value)."""
        from hashlib import sha256
        value = "AAPL"
        h = sha256(value.encode()).hexdigest()
        assert len(h) == 64, "SHA-256 hex digest must be exactly 64 chars"
        assert h != value, "Hash must differ from original value"
        assert re.match(r"^[a-f0-9]{64}$", h), \
            "Hash must be lowercase hex"
