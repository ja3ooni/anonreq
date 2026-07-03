"""Tests for HostnameMatcher.

Per D-001, D-002:
- Supports exact, wildcard, multi-level domain, and CIDR IP matching
- Returns MatchResult with provider, confidence, match_type, signature
- No match returns None
"""

from __future__ import annotations

from anonreq.discovery.hostname_matcher import HostnameMatcher, MatchResult
from anonreq.discovery.hostname_signatures import AI_SIGNATURES, ProviderSignature


class TestHostnameMatcher:
    """Test suite for HostnameMatcher."""

    def setup_method(self):
        self.matcher = HostnameMatcher(AI_SIGNATURES)

    def test_exact_match_returns_provider(self):
        """Exact hostname match returns correct provider."""
        result = self.matcher.match("api.openai.com")
        assert result is not None
        assert result.provider == "openai"
        assert result.match_type == "exact"
        assert result.confidence == 1.0

    def test_wildcard_match(self):
        """Wildcard pattern matches subdomain hostnames."""
        result = self.matcher.match("some.random.openai.com")
        assert result is not None
        assert result.provider == "openai"
        assert result.match_type == "wildcard"

    def test_no_match_returns_none(self):
        """Unknown hostname returns None."""
        result = self.matcher.match("nonexistent.example.com")
        assert result is None

    def test_match_ip_cidr(self):
        """CIDR IP range match returns correct provider."""
        result = self.matcher.match_ip("104.18.1.1")
        assert result is not None
        assert result.match_type == "cidr"
        assert result.confidence == 0.8

    def test_match_ip_no_match(self):
        """Unknown IP returns None."""
        result = self.matcher.match_ip("1.1.1.1")
        assert result is None

    def test_match_ip_invalid(self):
        """Invalid IP string returns None."""
        result = self.matcher.match_ip("not_an_ip")
        assert result is None

    def test_match_any_with_hostname(self):
        """match_any prefers hostname match over IP."""
        result = self.matcher.match_any(hostname="api.openai.com", ip="104.18.1.1")
        assert result is not None
        assert result.provider == "openai"
        assert result.match_type == "exact"

    def test_match_any_with_ip_fallback(self):
        """match_any falls back to IP when hostname has no match."""
        result = self.matcher.match_any(hostname="unknown.example.com", ip="104.18.1.1")
        assert result is not None
        assert result.match_type == "cidr"

    def test_match_any_no_match(self):
        """match_any returns None when neither hostname nor IP matches."""
        result = self.matcher.match_any(hostname="unknown.example.com", ip="1.1.1.1")
        assert result is None

    def test_refresh_signatures(self):
        """refresh_signatures reloads signatures for hot-reload."""
        new_sigs = [
            ProviderSignature("custom", ["custom.api.com"], tier="unknown", jurisdiction="other")
        ]
        self.matcher.refresh_signatures(new_sigs)
        result = self.matcher.match("custom.api.com")
        assert result is not None
        assert result.provider == "custom"
        # Original sigs should not match after refresh
        result2 = self.matcher.match("api.openai.com")
        assert result2 is None

    def test_match_result_fields(self):
        """MatchResult contains all required fields."""
        sig = AI_SIGNATURES[0]
        result = MatchResult(
            provider="openai",
            confidence=1.0,
            match_type="exact",
            signature=sig,
        )
        assert result.provider == "openai"
        assert result.confidence == 1.0
        assert result.match_type == "exact"
        assert result.signature is sig
