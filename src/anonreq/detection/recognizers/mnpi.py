"""MNPI (Material Non-Public Information) Recognizer.

Per D-001, D-002, D-003:
- Detects ticker symbols (NYSE/NASDAQ 1-4 uppercase letters, optional dot suffix)
- Detects deal codenames (Project/Operation/Initiative patterns)
- Optionally checks tenant restricted-names list
- Filters excluded words and short matches
- Deduplicates overlapping matches (shorter match loses)

Per D-004: MNPI audit events stored in dedicated MinIO WORM bucket.
Per T-15-01-01: All detection happens in-memory; only hashed values stored in audit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class MNPIConfig:
    """Configuration for the MNPI recognizer.

    Attributes:
        ticker_pattern: Regex pattern for ticker symbol matching.
        deal_codename_patterns: List of regex patterns for deal codename matching.
        excluded_words: Set of words to exclude from ticker detection.
        min_ticker_length: Minimum character length for ticker detection.
        score: Confidence score for MNPI detections (0.0-1.0).
    """

    ticker_pattern: str
    deal_codename_patterns: list[str]
    excluded_words: set[str] = field(default_factory=set)
    min_ticker_length: int = 2
    score: float = 0.85

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MNPIConfig":
        """Create MNPIConfig from a dictionary (e.g. parsed YAML).

        Args:
            data: Dictionary with configuration keys.

        Returns:
            A new MNPIConfig instance.
        """
        return cls(
            ticker_pattern=str(data["ticker_pattern"]),
            deal_codename_patterns=list(data.get("deal_codename_patterns", [])),
            excluded_words=set(data.get("excluded_words", [])),
            min_ticker_length=int(data.get("min_ticker_length", 2)),
            score=float(data.get("score", 0.85)),
        )


class MNPIRecognizer:
    """Recognizes Material Non-Public Information in text.

    Detects:
    - Ticker symbols (e.g. ``AAPL``, ``BRK.A``)
    - Deal codenames (e.g. ``Project Olympus``, ``Operation GoldenEye``)
    - Tenant restricted names (if ``RestrictedNamesManager`` provided)

    Returns detection dicts compatible with the AnonReq detection pipeline,
    with fields: ``entity_type``, ``start``, ``end``, ``score``, ``source``.
    """

    def __init__(
        self,
        config: MNPIConfig,
        restricted_names: Any | None = None,
    ) -> None:
        """Initialise the recognizer.

        Args:
            config: MNPIConfig with pattern and threshold settings.
            restricted_names: Optional RestrictedNamesManager for tenant
                restricted-name detection.
        """
        self._config = config
        self._restricted_names = restricted_names
        self._ticker_re = re.compile(config.ticker_pattern)
        self._deal_patterns = [
            re.compile(p) for p in config.deal_codename_patterns
        ]
        self._excluded = {w.upper() for w in config.excluded_words}

    @property
    def config(self) -> MNPIConfig:
        """Return the recognizer configuration."""
        return self._config

    def analyze(
        self,
        text: str,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Analyze text for MNPI content.

        Args:
            text: The text to analyze.
            tenant_id: Optional tenant ID for restricted-name lookup.

        Returns:
            List of detection dicts with keys: ``entity_type``, ``start``,
            ``end``, ``score``, ``source``.
        """
        results: list[dict[str, Any]] = []
        results.extend(self._detect_tickers(text))
        results.extend(self._detect_deal_codenames(text))

        if tenant_id is not None and self._restricted_names is not None:
            results.extend(self._detect_restricted_names(text, tenant_id))

        # Deduplicate overlapping matches (shorter match loses)
        results = self._deduplicate(results)

        return results

    def _detect_tickers(self, text: str) -> list[dict[str, Any]]:
        """Detect ticker symbols in text.

        Returns detection dicts for ticker matches that pass length and
        exclusion checks.
        """
        results: list[dict[str, Any]] = []
        for match in self._ticker_re.finditer(text):
            raw = match.group()
            # Skip if word is in excluded list
            if raw.upper() in self._excluded:
                continue
            # Skip if the core ticker part is too short
            core = raw.split(".")[0]
            if len(core) < self._config.min_ticker_length:
                continue

            results.append({
                "entity_type": "MNPI_TICKER",
                "start": match.start(),
                "end": match.end(),
                "score": self._config.score,
                "source": "mnpi",
            })

        return results

    def _detect_deal_codenames(self, text: str) -> list[dict[str, Any]]:
        """Detect deal codenames in text.

        Matches patterns like ``Project <Name>``, ``Operation <Name>``,
        ``Initiative <Name>``.
        """
        results: list[dict[str, Any]] = []
        for pattern in self._deal_patterns:
            for match in pattern.finditer(text):
                results.append({
                    "entity_type": "MNPI_DEAL",
                    "start": match.start(),
                    "end": match.end(),
                    "score": self._config.score,
                    "source": "mnpi",
                })

        return results

    def _detect_restricted_names(
        self,
        text: str,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Detect tenant restricted names in text.

        Performs case-insensitive substring matching.
        """
        results: list[dict[str, Any]] = []
        if self._restricted_names is None:
            return results

        matched = self._restricted_names.check_name(tenant_id, text)
        if matched:
            names = self._restricted_names.get_names(tenant_id)
            text_upper = text.upper()
            for name in names:
                start = text_upper.find(name.upper())
                if start >= 0:
                    results.append({
                        "entity_type": "MNPI_RESTRICTED_NAME",
                        "start": start,
                        "end": start + len(name),
                        "score": self._config.score,
                        "source": "mnpi",
                    })

        return results

    def _deduplicate(
        self,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove overlapping matches keeping the longest.

        When two detections overlap, the shorter match is removed.
        This prevents e.g. ticker ``A`` within ``APPLE`` being detected
        when ``APPLE`` is not a ticker.
        """
        if not results:
            return results

        # Sort by start position, then by length descending
        sorted_results = sorted(
            results,
            key=lambda r: (r["start"], -(r["end"] - r["start"])),
        )

        deduped: list[dict[str, Any]] = []
        for result in sorted_results:
            if not deduped:
                deduped.append(result)
                continue

            last = deduped[-1]
            # If this result overlaps with the last one
            if result["start"] < last["end"]:
                # Keep the longer one (already sorted by length desc)
                continue

            deduped.append(result)

        return deduped


def create_mnpi_bundle(
    config_path: str = "config/mnpi_recognizers.yaml",
    restricted_names_mgr: Any | None = None,
) -> list[MNPIRecognizer]:
    """Create and return a list of MNPI recognizers.

    Loads configuration from the given YAML path, creates an
    ``MNPIRecognizer`` instance, and returns it as a single-element
    list (for registration in the detection pipeline).

    Args:
        config_path: Path to the MNPI recognizer YAML configuration.
        restricted_names_mgr: Optional ``RestrictedNamesManager`` for
            tenant restricted-name detection.

    Returns:
        A list containing one ``MNPIRecognizer`` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    with open(config_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    mnpi_data = data.get("mnpi", data)
    config = MNPIConfig.from_dict(mnpi_data)
    return [MNPIRecognizer(config=config, restricted_names=restricted_names_mgr)]
