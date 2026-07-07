"""AI API traffic and certificate-pinning detection for transparent proxy mode."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


AI_API_DOMAINS: Final[list[str]] = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "gemini.google.com",
    "api.mistral.ai",
    "api.deepseek.com",
    "api.cohere.ai",
    "api.together.xyz",
    "api.perplexity.ai",
    "localhost",
    "127.0.0.1",
]

AI_API_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"^/v1/(chat/completions|completions|embeddings|messages|models)$", re.I),
    re.compile(r"^/v1/(responses|assistants|threads|runs)", re.I),
    re.compile(r"^/v1beta/models/.+:(generateContent|streamGenerateContent)$", re.I),
    re.compile(r"^/api/(chat|generate|embeddings)$", re.I),
]


@dataclass(frozen=True)
class TrafficDecision:
    """Classification result for an intercepted request."""

    classification: str
    host: str
    path: str
    method: str
    reason: str

    @property
    def is_ai(self) -> bool:
        return self.classification == "ai"


class AITrafficDetector:
    """Classify intercepted traffic by AI provider hostname and API path."""

    def __init__(
        self,
        domains: list[str] | None = None,
        path_patterns: list[re.Pattern[str]] | None = None,
    ) -> None:
        self.domains = [d.lower().strip(".") for d in (domains or AI_API_DOMAINS)]
        self.path_patterns = list(path_patterns or AI_API_PATTERNS)

    def is_ai_traffic(self, host: str, path: str) -> bool:
        host_match = self._host_matches(host)
        path_match = any(pattern.search(path or "/") for pattern in self.path_patterns)
        return host_match and path_match

    def classify(self, host: str, path: str, method: str) -> str:
        return self.classify_request(host, path, method).classification

    def classify_request(self, host: str, path: str, method: str) -> TrafficDecision:
        clean_host = self._normalize_host(host)
        if self.is_ai_traffic(clean_host, path):
            return TrafficDecision("ai", clean_host, path, method, "known_ai_host_and_path")
        if self._host_matches(clean_host):
            return TrafficDecision("unknown", clean_host, path, method, "known_ai_host_unknown_path")
        return TrafficDecision("non_ai", clean_host, path, method, "host_not_in_ai_registry")

    def _host_matches(self, host: str) -> bool:
        clean_host = self._normalize_host(host)
        for domain in self.domains:
            if clean_host == domain or clean_host.endswith(f".{domain}"):
                return True
        return False

    @staticmethod
    def _normalize_host(host: str) -> str:
        return (host or "").split(":", 1)[0].strip().strip(".").lower()


class CertPinningDetector:
    """Heuristic detector for certificate pinning signals.

    TLS ClientHello does not explicitly announce pinning. This class detects
    common enterprise-observable failure signals and testable client markers,
    then lets policy decide fail-closed block vs fail-open passthrough.
    """

    PINNING_MARKERS: Final[tuple[bytes, ...]] = (
        b"certificate pinning",
        b"pin-sha256",
        b"public-key-pins",
        b"x509_verify_cert_error",
        b"bad certificate",
        b"unknown ca",
    )

    def check_pinning(self, client_hello: bytes, domain: str) -> bool:
        if not client_hello:
            return False
        lowered = client_hello.lower()
        if any(marker in lowered for marker in self.PINNING_MARKERS):
            return True

        # Some pinned desktop SDKs omit SNI. Treat that as suspicious only for
        # known AI API domains, where transparent interception expects SNI.
        normalized_domain = (domain or "").lower()
        return bool(normalized_domain and normalized_domain.encode("ascii", "ignore") not in lowered)
