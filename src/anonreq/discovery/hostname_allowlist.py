"""Hostname allowlist for AI provider detection.

Provides:
- ``HostnameAllowlist`` — class-based wrapper around the provider signature
  database with hostname matching (wildcard), IP CIDR matching, and runtime
  provider configuration overrides.
- ``MatchResult`` — dataclass for match results with provider, confidence,
  and match type.

Per D-007, D-008, D-010:
- Matches by hostname (exact and wildcard) with confidence 1.0
- Matches by IP (CIDR range) with confidence 0.9
- Returns ``MatchResult`` with provider name, confidence score, and type
- Provides ``get_all_proxy_domains()`` for PAC file generation
"""

from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from typing import Any

from anonreq.discovery.ai_signatures import (
    AI_PROVIDER_SIGNATURES,
    get_provider_by_hostname,
    get_provider_by_ip,
)


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a target against the AI provider allowlist.

    Attributes:
        provider: Name of the matched AI provider.
        confidence: Confidence score (1.0 for hostname, 0.9 for IP range).
        match_type: How the match was made (``hostname`` or ``ip_range``).
    """

    provider: str
    confidence: float
    match_type: str


class HostnameAllowlist:
    """Matches hostnames and IPs against known AI provider signatures.

    Wraps the ``ai_signatures`` module with a class-based interface
    suitable for dependency injection and runtime configuration.

    Args:
        signatures: Optional list of provider signature dicts to use instead
            of the default ``AI_PROVIDER_SIGNATURES``.
    """

    def __init__(self, signatures: list[dict[str, Any]] | None = None) -> None:
        self._signatures: list[dict[str, Any]] = (
            list(signatures) if signatures is not None
            else list(AI_PROVIDER_SIGNATURES)
        )
        # Runtime provider config overrides
        self._overrides: dict[str, dict[str, Any]] = {}

    def _get_effective_signature(
        self, provider: str,
    ) -> dict[str, Any] | None:
        """Get a provider's signature with any runtime overrides applied."""
        for sig in self._signatures:
            if sig["provider"] == provider:
                merged = dict(sig)
                if provider in self._overrides:
                    merged.update(self._overrides[provider])
                return merged
        return None

    def match_hostname(self, hostname: str) -> MatchResult | None:
        """Match a hostname against known AI provider domains.

        Supports exact and wildcard matching. Returns the first match
        with confidence 1.0.

        Args:
            hostname: The hostname to match (e.g. ``api.openai.com``).

        Returns:
            ``MatchResult`` if a provider matches, ``None`` otherwise.
        """
        hostname = hostname.lower()

        # Merge overrides into a searchable structure
        all_signatures = list(self._signatures)
        for provider, override in self._overrides.items():
            existing = self._get_effective_signature(provider)
            if existing:
                # Already merged via override
                pass
            else:
                # New provider from override
                merged = dict(override)
                merged["provider"] = provider
                all_signatures.append(merged)

        # Exact match first
        for sig in all_signatures:
            for pattern in sig.get("hostnames", []):
                clean = pattern.lower().replace("*.", "")
                if hostname == clean:
                    return MatchResult(
                        provider=sig["provider"],
                        confidence=1.0,
                        match_type="hostname",
                    )

        # Wildcard match
        for sig in all_signatures:
            for pattern in sig.get("hostnames", []):
                if "*" in pattern and fnmatch.fnmatch(hostname, pattern.lower()):
                    return MatchResult(
                        provider=sig["provider"],
                        confidence=1.0,
                        match_type="hostname",
                    )

        # Fall back to the standalone module function
        result = get_provider_by_hostname(hostname)
        if result is not None:
            return MatchResult(
                provider=result["provider"],
                confidence=1.0,
                match_type="hostname",
            )

        return None

    def match_ip(self, ip_str: str) -> MatchResult | None:
        """Match an IP address against provider CIDR ranges.

        Args:
            ip_str: The IP address as a string.

        Returns:
            ``MatchResult`` with confidence 0.9 if a provider matches,
            ``None`` otherwise.
        """
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return None

        all_signatures = list(self._signatures)
        for provider, override in self._overrides.items():
            existing = self._get_effective_signature(provider)
            if existing and existing.get("ip_ranges"):
                pass  # Already in signatures via override merge
            elif override.get("ip_ranges"):
                all_signatures.append({
                    "provider": provider,
                    **override,
                })

        for sig in all_signatures:
            for cidr in sig.get("ip_ranges", []):
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if addr in network:
                        return MatchResult(
                            provider=sig["provider"],
                            confidence=0.9,
                            match_type="ip_range",
                        )
                except ValueError:
                    continue

        # Fall back to standalone module function
        result = get_provider_by_ip(ip_str)
        if result is not None:
            return MatchResult(
                provider=result["provider"],
                confidence=0.9,
                match_type="ip_range",
            )

        return None

    def match_request(
        self,
        target_host: str,
        target_ip: str | None = None,
    ) -> MatchResult | None:
        """Match a full request target (hostname + optional IP).

        Hostname match is preferred and checked first.  Falls back to
        IP match if no hostname match found.

        Args:
            target_host: The target hostname.
            target_ip: Optional target IP address.

        Returns:
            The best ``MatchResult`` available, or ``None``.
        """
        # Hostname match is preferred (higher confidence)
        hostname_result = self.match_hostname(target_host)
        if hostname_result is not None:
            return hostname_result

        # Fall back to IP match
        if target_ip is not None:
            return self.match_ip(target_ip)

        return None

    def get_all_proxy_domains(self) -> list[str]:
        """Return all unique hostname patterns for PAC file generation.

        Collects hostnames from all known provider signatures.

        Returns:
            A list of unique hostname pattern strings.
        """
        domains: set[str] = set()
        for sig in self._signatures:
            for hostname in sig.get("hostnames", []):
                domains.add(hostname)
        # Also include overrides
        for provider, override in self._overrides.items():
            for hostname in override.get("hostnames", []):
                domains.add(hostname)
        return sorted(domains)

    def set_provider_config(self, provider: str, config: dict[str, Any]) -> None:
        """Override signature data for a provider at runtime.

        Merges the given config with the existing provider signature.
        Allows custom provider configuration without modifying the
        signature database.

        Args:
            provider: Provider name (e.g. ``"openai"``).
            config: Config dict with fields to override (e.g.
                ``{"hostnames": ["custom.openai.com"]}``).
        """
        self._overrides[provider] = config
