"""Tests for AI hostname allowlist (Plan 17-02, Task 2).

Per D-007, D-008, D-010, D-011:
- HostnameAllowlist matches exact AI provider domains
- HostnameAllowlist matches wildcard subdomains
- HostnameAllowlist matches by CIDR IP range
- HostnameAllowlist returns provider name and confidence for matches
- HostnameAllowlist returns None for non-AI domains
- get_all_proxy_domains returns all unique hostname patterns
"""

from __future__ import annotations

import pytest

from anonreq.discovery.ai_signatures import (
    AI_PROVIDER_SIGNATURES,
    get_provider_by_hostname,
    get_provider_by_ip,
    get_provider_by_path,
)


class TestAISignatures:
    """Test suite for the AI provider signature database."""

    def test_signatures_has_20_plus_providers(self):
        """AI_PROVIDER_SIGNATURES contains 20+ providers."""
        assert len(AI_PROVIDER_SIGNATURES) >= 20

    def test_get_provider_by_hostname_exact(self):
        """Exact hostname match returns correct provider."""
        result = get_provider_by_hostname("api.openai.com")
        assert result is not None
        assert result["provider"] == "openai"

    def test_get_provider_by_hostname_wildcard(self):
        """Wildcard hostname matches subdomains."""
        result = get_provider_by_hostname("oaksvc.openai.com")
        assert result is not None
        assert result["provider"] in ("openai",)

    def test_get_provider_by_hostname_returns_none(self):
        """Unknown hostname returns None."""
        result = get_provider_by_hostname("unknown.example.com")
        assert result is None

    def test_get_provider_by_ip_cidr(self):
        """CIDR IP range match returns correct provider."""
        result = get_provider_by_ip("104.18.1.1")
        assert result is not None

    def test_get_provider_by_ip_none(self):
        """Unknown IP returns None."""
        result = get_provider_by_ip("1.1.1.1")
        assert result is None

    def test_get_provider_by_path_known(self):
        """Known AI API path returns matching provider."""
        result = get_provider_by_path("/v1/chat/completions")
        assert result is not None

    def test_get_provider_by_path_none(self):
        """Unknown path returns None."""
        result = get_provider_by_path("/api/health")
        assert result is None

    def test_provider_has_required_fields(self):
        """Every provider signature has required fields."""
        for sig in AI_PROVIDER_SIGNATURES:
            assert "provider" in sig
            assert "hostnames" in sig
            assert isinstance(sig["hostnames"], list)
            assert "tier" in sig
            assert "jurisdiction" in sig

    def test_providers_include_major_ones(self):
        """Major providers are in the signature database."""
        provider_names = {s["provider"] for s in AI_PROVIDER_SIGNATURES}
        for expected in ("openai", "anthropic", "gemini", "bedrock", "azure_openai"):
            assert expected in provider_names, f"Missing provider: {expected}"

    def test_providers_include_regional_ones(self):
        """Regional providers are in the signature database."""
        provider_names = {s["provider"] for s in AI_PROVIDER_SIGNATURES}
        for expected in (
            "mistral", "cohere", "groq", "together", "perplexity",
            "deepseek", "xai", "fireworks", "replicate", "huggingface",
            "meta_llama", "alibaba_cloud",
        ):
            assert expected in provider_names, f"Missing provider: {expected}"


class TestHostnameAllowlist:
    """Test suite for HostnameAllowlist."""

    def setup_method(self):
        from anonreq.discovery.hostname_allowlist import HostnameAllowlist
        self.wl = HostnameAllowlist()

    def test_match_hostname_openai(self):
        """Match api.openai.com returns openai provider."""
        result = self.wl.match_hostname("api.openai.com")
        assert result is not None
        assert result.provider == "openai"
        assert result.confidence == 1.0
        assert result.match_type == "hostname"

    def test_match_hostname_wildcard_anthropic(self):
        """Wildcard *.anthropic.com matches subdomains."""
        result = self.wl.match_hostname("api.anthropic.com")
        assert result is not None
        assert result.provider == "anthropic"
        assert result.confidence == 1.0  # exact match via wildcard supported

    def test_match_hostname_returns_none(self):
        """Unknown domain returns None."""
        result = self.wl.match_hostname("unknown.example.com")
        assert result is None

    def test_match_hostname_wildcard_subdomain(self):
        """Wildcard pattern matches nested subdomains."""
        result = self.wl.match_hostname("some.random.openai.com")
        assert result is not None
        assert result.provider == "openai"

    def test_match_ip_cidr(self):
        """CIDR IP match returns provider with reduced confidence."""
        result = self.wl.match_ip("104.18.1.1")
        assert result is not None
        assert result.confidence == 0.9
        assert result.match_type == "ip_range"

    def test_match_ip_returns_none(self):
        """Unknown IP returns None."""
        result = self.wl.match_ip("10.0.0.1")
        assert result is None

    def test_match_ip_invalid(self):
        """Invalid IP string returns None."""
        result = self.wl.match_ip("not-an-ip")
        assert result is None

    def test_match_request_hostname_wins(self):
        """match_request prefers hostname match over IP."""
        result = self.wl.match_request(
            target_host="api.openai.com",
            target_ip="104.18.1.1",
        )
        assert result is not None
        assert result.provider == "openai"
        assert result.match_type == "hostname"

    def test_match_request_ip_fallback(self):
        """match_request falls back to IP when hostname unknown."""
        result = self.wl.match_request(
            target_host="unknown.example.com",
            target_ip="104.18.1.1",
        )
        assert result is not None

    def test_get_all_proxy_domains(self):
        """get_all_proxy_domains returns non-empty list of domains."""
        domains = self.wl.get_all_proxy_domains()
        assert len(domains) > 0
        # Should include major provider domains
        all_domains = " ".join(domains).lower()
        assert "openai" in all_domains

    def test_set_provider_config(self):
        """set_provider_config overrides provider data."""
        self.wl.set_provider_config("openai", {"hostnames": ["custom.openai.com"]})
        result = self.wl.match_hostname("custom.openai.com")
        assert result is not None
        assert result.provider == "openai"

    def test_match_gemini(self):
        """Match gemini provider."""
        result = self.wl.match_hostname("generativelanguage.googleapis.com")
        assert result is not None
        assert result.provider == "gemini"

    def test_match_mistral(self):
        """Match mistral provider."""
        result = self.wl.match_hostname("api.mistral.ai")
        assert result is not None
        assert result.provider == "mistral"
