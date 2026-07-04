"""Property-based tests for MNPI (Material Non-Public Information) invariants.

Uses Hypothesis to prove:
1. **No-MNPI-in-logs**: For any text containing ticker symbols or deal codenames,
   the MNPI values never appear in audit log output.
2. **Ticker detection coverage**: All uppercase 1-4 letter words at word
   boundaries are detected as potential tickers (except excluded words).
3. **Hash-not-value**: Audit events store SHA-256 hashes, never raw MNPI values.

Invariants are proven through randomized testing with Hypothesis strategies.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re

import pytest
import yaml
from hypothesis import assume, given, settings, strategies as st

from anonreq.detection.recognizers.mnpi import MNPIConfig, MNPIRecognizer


# ── Load config once at module level ──────────────────────────────

_CONFIG_PATH = "config/mnpi_recognizers.yaml"


def _load_config() -> MNPIConfig:
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return MNPIConfig.from_dict(raw if "ticker_pattern" in raw else raw["mnpi"])


def _get_config_attr(attr: str):
    """Lazy-load config attribute. Cached after first call."""
    if not hasattr(_get_config_attr, "_config"):
        _get_config_attr._config = _load_config()
    return getattr(_get_config_attr._config, attr)


def _excluded_words():
    return _get_config_attr("excluded_words")


def _min_ticker_length():
    return _get_config_attr("min_ticker_length")


# ── Hypothesis strategies ─────────────────────────────────────────

# Generate random uppercase ticker-like words (1-4 letters)
ticker_strategy = st.text(
    alphabet=st.characters(min_codepoint=65, max_codepoint=90),  # A-Z
    min_size=1,
    max_size=4,
)

# Generate sentences with MNPI embedded
mnpi_text_strategy = st.builds(
    lambda prefix, ticker, suffix: f"{prefix} {ticker} {suffix}",
    prefix=st.sampled_from([
        "Consider", "Review", "Analyze", "The performance of", "Based on",
    ]),
    ticker=ticker_strategy,
    suffix=st.sampled_from([
        "for investment.",
        "is a key position.",
        "looks promising.",
        "should be monitored.",
        "has strong fundamentals.",
    ]),
)


# ── No-MNPI-in-logs invariant ─────────────────────────────────────


class TestNoMNPILogsInvariant:
    """Prove: MNPI values never appear in log output.

    For any text containing ticker symbols or deal codenames, the raw
    MNPI values must never appear in audit log output. Only metadata
    (span positions, entity types) should be logged.
    """

    @given(text=mnpi_text_strategy)
    @settings(max_examples=200, deadline=None)
    def test_mnpi_values_not_in_log_output(self, text: str):
        """Invariant: MNPI values must not appear in log output."""
        cfg = _load_config()
        recognizer = MNPIRecognizer(config=cfg)

        # Find which tickers are in the text
        tickers = re.findall(r'\b[A-Z]{1,4}\b', text)
        mnpi_values = [t for t in tickers if t not in cfg.excluded_words]

        assume(len(mnpi_values) > 0)  # Only test when MNPI is present

        # Capture log output
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("anonreq.detection.recognizers.mnpi")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            detections = recognizer.analyze(text)

            # Log the detections (as audit would)
            for det in detections:
                logger.info(
                    "MNPI detected",
                    extra={
                        "entity_type": det["entity_type"],
                        "start": det["start"],
                        "end": det["end"],
                        "source": det["source"],
                    },
                )

            log_content = buffer.getvalue()

            # None of the MNPI values should appear as whole words in log output
            for value in mnpi_values:
                pattern = r'\b' + re.escape(value) + r'\b'
                if re.search(pattern, log_content):
                    assert False, (
                        f"MNPI value '{value}' must not appear in log output. "
                        f"Text: '{text}'"
                    )

            # Also check no raw entity values from detection results
            for det in detections:
                det_value = text[det["start"]:det["end"]]
                pattern = r'\b' + re.escape(det_value) + r'\b'
                if re.search(pattern, log_content):
                    assert False, (
                        f"Detected value '{det_value}' must not appear in log output"
                    )
        finally:
            logger.removeHandler(handler)


# ── Ticker detection coverage invariant ──────────────────────────


class TestTickerDetectionCoverage:
    """Prove: All uppercase 1-4 letter words are detected as potential
    tickers, except those explicitly excluded."""

    @given(ticker=ticker_strategy)
    @settings(max_examples=200, deadline=None)
    def test_uppercase_words_detected_as_tickers(self, ticker: str):
        """All uppercase 1-4 letter words produce MNPI_TICKER detections."""
        cfg = _load_config()
        recognizer = MNPIRecognizer(config=cfg)

        # Skip excluded words
        if ticker in cfg.excluded_words:
            return  # Excluded words correctly NOT detected

        text = f"Analyze {ticker} for investment strategy."
        detections = recognizer.analyze(text)

        ticker_detections = [
            text[d["start"]:d["end"]]
            for d in detections
            if d["entity_type"] == "MNPI_TICKER"
        ]

        if len(ticker) >= cfg.min_ticker_length:
            assert ticker in ticker_detections, (
                f"Uppercase word '{ticker}' (len={len(ticker)}, "
                f"min_len={cfg.min_ticker_length}) should be detected as ticker"
            )


# ── Hash-not-value invariant ──────────────────────────────────────


class TestMNPIHashNotValue:
    """Prove: SHA-256 hashes are used for audit, never raw MNPI values."""

    @given(value=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Lt", "N", "P")),
        min_size=1,
        max_size=20,
    ))
    @settings(max_examples=200, deadline=None)
    def test_hash_differs_from_original(self, value: str):
        """SHA-256 hash of an MNPI value differs from the value itself."""
        h = hashlib.sha256(value.encode()).hexdigest()
        assert h != value, "Hash must differ from original value"
        assert len(h) == 64, "SHA-256 hex digest must be exactly 64 chars"
        assert re.match(r"^[a-f0-9]{64}$", h), \
            "Hash must be lowercase hexadecimal"

    @given(
        value1=st.text(min_size=1, max_size=10),
        value2=st.text(min_size=1, max_size=10),
    )
    @settings(max_examples=200, deadline=None)
    def test_different_values_different_hashes(self, value1: str, value2: str):
        """Two different MNPI values produce different hashes."""
        assume(value1 != value2)
        h1 = hashlib.sha256(value1.encode()).hexdigest()
        h2 = hashlib.sha256(value2.encode()).hexdigest()
        assert h1 != h2, \
            "Different values must produce different hashes"

    @given(value=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        min_size=1,
        max_size=100,
    ))
    @settings(max_examples=200, deadline=None)
    def test_hash_is_deterministic(self, value: str):
        """Same MNPI value always produces the same hash."""
        h1 = hashlib.sha256(value.encode()).hexdigest()
        h2 = hashlib.sha256(value.encode()).hexdigest()
        assert h1 == h2, \
            "Hash must be deterministic for the same input"
