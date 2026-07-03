"""Hostname and IP matching against AI provider signature database.

Per D-001, D-002:
- Supports exact, wildcard, multi-level domain, and CIDR IP matching
- Returns MatchResult with provider, confidence, match_type, signature
- No match returns None
"""

from __future__ import annotations

import fnmatch
import ipaddress
from typing import Any

from anonreq.discovery.hostname_signatures import ProviderSignature


class MatchResult:
    """Result of matching a hostname or IP against provider signatures.

    Attributes:
        provider: Name of the matched provider.
        confidence: Confidence score (1.0 for exact, 0.8 for CIDR, etc.).
        match_type: Type of match — "exact", "wildcard", "cidr".
        signature: The ProviderSignature that matched.
    """

    __slots__ = ("provider", "confidence", "match_type", "signature")

    def __init__(
        self,
        provider: str,
        confidence: float,
        match_type: str,
        signature: ProviderSignature,
    ) -> None:
        self.provider = provider
        self.confidence = confidence
        self.match_type = match_type
        self.signature = signature

    def __repr__(self) -> str:
        return (
            f"MatchResult(provider={self.provider!r}, confidence={self.confidence}, "
            f"match_type={self.match_type!r})"
        )


class HostnameMatcher:
    """Matches hostnames and IPs against provider signatures.

    Args:
        signatures: List of ProviderSignature to match against.
    """

    def __init__(self, signatures: list[ProviderSignature]) -> None:
        self._signatures = signatures

    def match(self, hostname: str) -> MatchResult | None:
        """Match a hostname against signatures.

        Checks exact match first, then wildcard patterns.
        Returns the highest-confidence match (exact > wildcard).

        Args:
            hostname: The hostname to match.

        Returns:
            MatchResult if found, None otherwise.
        """
        hostname = hostname.lower()

        for sig in self._signatures:
            for pattern in sig.hostnames:
                if hostname == pattern.lower().replace("*.", ""):
                    return MatchResult(sig.provider, 1.0, "exact", sig)

        for sig in self._signatures:
            for pattern in sig.hostnames:
                if fnmatch.fnmatch(hostname, pattern.lower()):
                    return MatchResult(sig.provider, 0.95, "wildcard", sig)

        return None

    def match_ip(self, ip: str) -> MatchResult | None:
        """Match an IP address against signature CIDR ranges.

        Args:
            ip: The IP address to match.

        Returns:
            MatchResult if found, None otherwise.
        """
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None

        for sig in self._signatures:
            for cidr in sig.ip_ranges:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if addr in network:
                        return MatchResult(sig.provider, 0.8, "cidr", sig)
                except ValueError:
                    continue

        return None

    def match_any(
        self,
        hostname: str | None = None,
        ip: str | None = None,
    ) -> MatchResult | None:
        """Try hostname match first, fall back to IP match.

        Hostname match has higher confidence and is preferred.

        Args:
            hostname: Optional hostname to match.
            ip: Optional IP address to match.

        Returns:
            MatchResult from hostname (preferred) or IP, None otherwise.
        """
        if hostname:
            result = self.match(hostname)
            if result:
                return result

        if ip:
            return self.match_ip(ip)

        return None

    def refresh_signatures(self, signatures: list[ProviderSignature]) -> None:
        """Reload signatures for hot-reload support."""
        self._signatures = signatures
