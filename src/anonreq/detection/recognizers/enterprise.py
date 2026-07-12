"""Enterprise recognizers for secret and internal hostname detection.

Per GUARD-01:
- Detects OpenAI-style API keys (sk-/pk-/sk-proj-)
- Detects AWS access keys (AKIA...)
- Detects GitHub tokens (ghp_/ghs_/gho_/ghu_/ghr_/ghb_)
- Detects internal hostnames based on a configurable list of domains
- Integrates into the detection stage after core and MNPI detection
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class EnterpriseRecognizerConfig:
    """Configuration for an individual enterprise recognizer.

    Attributes:
        enabled: Whether the recognizer is active.
        confidence: Confidence score for detections (0.0-1.0).
        patterns: Regex patterns for matching.
        internal_domains: Configurable domain list for hostname matching.
    """

    enabled: bool = True
    confidence: float = 0.85
    patterns: list[str] = field(default_factory=list)
    internal_domains: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnterpriseRecognizerConfig:
        """Create config from a dictionary."""
        patterns = []
        if "pattern" in data and data["pattern"]:
            patterns.append(data["pattern"])
        elif "patterns" in data:
            patterns = list(data["patterns"])

        return cls(
            enabled=bool(data.get("enabled", True)),
            confidence=float(data.get("confidence", 0.85)),
            patterns=patterns,
            internal_domains=list(data.get("internal_domains", [])),
        )


class AnonReq_APIKeyRecognizer:
    """Detects API keys (OpenAI-style sk-, pk-, sk-proj-) in text."""

    name = "AnonReq_APIKeyRecognizer"

    def __init__(self, config: EnterpriseRecognizerConfig) -> None:
        self._config = config
        # Use default if no patterns specified in config
        patterns = config.patterns if config.patterns else [
            r"\b(sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9]{20,})\b"
        ]
        self._regexes = [re.compile(p) for p in patterns]

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Scan text for API keys."""
        results: list[dict[str, Any]] = []
        for regex in self._regexes:
            for match in regex.finditer(text):
                results.append({
                    "entity_type": "ENTERPRISE_API_KEY",
                    "start": match.start(),
                    "end": match.end(),
                    "score": self._config.confidence,
                    "source": "enterprise",
                })
        return self._deduplicate(results)

    def _deduplicate(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return results
        sorted_results = sorted(
            results,
            key=lambda r: (r["start"], -(r["end"] - r["start"])),
        )
        deduped: list[dict[str, Any]] = []
        for r in sorted_results:
            if not deduped:
                deduped.append(r)
                continue
            last = deduped[-1]
            if r["start"] < last["end"]:
                continue
            deduped.append(r)
        return deduped


class AnonReq_AWSAccessKeyRecognizer:
    """Detects AWS Access Keys (AKIA...) in text."""

    name = "AnonReq_AWSAccessKeyRecognizer"

    def __init__(self, config: EnterpriseRecognizerConfig) -> None:
        self._config = config
        patterns = config.patterns if config.patterns else [
            r"\b(AKIA[0-9A-Z]{16})\b"
        ]
        self._regexes = [re.compile(p) for p in patterns]

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Scan text for AWS keys."""
        results: list[dict[str, Any]] = []
        for regex in self._regexes:
            for match in regex.finditer(text):
                results.append({
                    "entity_type": "ENTERPRISE_AWS_KEY",
                    "start": match.start(),
                    "end": match.end(),
                    "score": self._config.confidence,
                    "source": "enterprise",
                })
        return self._deduplicate(results)

    def _deduplicate(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return results
        sorted_results = sorted(
            results,
            key=lambda r: (r["start"], -(r["end"] - r["start"])),
        )
        deduped: list[dict[str, Any]] = []
        for r in sorted_results:
            if not deduped:
                deduped.append(r)
                continue
            last = deduped[-1]
            if r["start"] < last["end"]:
                continue
            deduped.append(r)
        return deduped


class AnonReq_GitHubTokenRecognizer:
    """Detects GitHub tokens (ghp_, ghs_, gho_, ghu_, ghr_, ghb_) in text."""

    name = "AnonReq_GitHubTokenRecognizer"

    def __init__(self, config: EnterpriseRecognizerConfig) -> None:
        self._config = config
        patterns = config.patterns if config.patterns else [
            r"\b(ghp_[a-zA-Z0-9]{36}|ghs_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|ghu_[a-zA-Z0-9]{36}|ghr_[a-zA-Z0-9]{36}|ghb_[a-zA-Z0-9]{36})\b"
        ]
        self._regexes = [re.compile(p) for p in patterns]

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Scan text for GitHub tokens."""
        results: list[dict[str, Any]] = []
        for regex in self._regexes:
            for match in regex.finditer(text):
                results.append({
                    "entity_type": "ENTERPRISE_GITHUB_TOKEN",
                    "start": match.start(),
                    "end": match.end(),
                    "score": self._config.confidence,
                    "source": "enterprise",
                })
        return self._deduplicate(results)

    def _deduplicate(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return results
        sorted_results = sorted(
            results,
            key=lambda r: (r["start"], -(r["end"] - r["start"])),
        )
        deduped: list[dict[str, Any]] = []
        for r in sorted_results:
            if not deduped:
                deduped.append(r)
                continue
            last = deduped[-1]
            if r["start"] < last["end"]:
                continue
            deduped.append(r)
        return deduped


class AnonReq_InternalHostnameRecognizer:
    """Detects internal hostnames matching a configurable domain list in text."""

    name = "AnonReq_InternalHostnameRecognizer"

    def __init__(self, config: EnterpriseRecognizerConfig) -> None:
        self._config = config
        domains = config.internal_domains
        cleaned_domains = []
        for d in domains:
            d = d.lstrip("*.").rstrip(".")
            if d:
                cleaned_domains.append(re.escape(d))

        if cleaned_domains:
            domain_pattern = "|".join(cleaned_domains)
            pattern_str = rf"\b([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+({domain_pattern})\b(?!\.[a-zA-Z0-9])"
            self._regex = re.compile(pattern_str)
        else:
            self._regex = None

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Scan text for internal hostnames."""
        results: list[dict[str, Any]] = []
        if self._regex is None:
            return results

        for match in self._regex.finditer(text):
            results.append({
                "entity_type": "ENTERPRISE_INTERNAL_HOST",
                "start": match.start(),
                "end": match.end(),
                "score": self._config.confidence,
                "source": "enterprise",
            })
        return self._deduplicate(results)

    def _deduplicate(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return results
        sorted_results = sorted(
            results,
            key=lambda r: (r["start"], -(r["end"] - r["start"])),
        )
        deduped: list[dict[str, Any]] = []
        for r in sorted_results:
            if not deduped:
                deduped.append(r)
                continue
            last = deduped[-1]
            if r["start"] < last["end"]:
                continue
            deduped.append(r)
        return deduped


def create_enterprise_bundle(
    config_path: str = "config/recognizers.yaml",
) -> dict[str, Any]:
    """Create and return a dictionary of enabled enterprise recognizers.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Dict mapping key names to recognizer instances.
    """
    with open(config_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    recognizers_data = data.get("enterprise_recognizers", {})
    bundle: dict[str, Any] = {}

    recognizer_classes = {
        "api_key": AnonReq_APIKeyRecognizer,
        "aws_access_key": AnonReq_AWSAccessKeyRecognizer,
        "github_token": AnonReq_GitHubTokenRecognizer,
        "internal_hostname": AnonReq_InternalHostnameRecognizer,
    }

    for key, cls in recognizer_classes.items():
        rec_data = recognizers_data.get(key, {})
        config = EnterpriseRecognizerConfig.from_dict(rec_data)
        if config.enabled:
            bundle[key] = cls(config)

    return bundle
