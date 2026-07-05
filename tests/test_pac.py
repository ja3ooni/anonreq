"""Tests for PAC file generation (Plan 17-02, Task 1).

Per D-007, D-009:
- GET /v1/proxy.pac returns valid PAC file with application/x-ns-proxy-autoconfig
- PAC file contains PROXY directive for all known AI provider domains
- PAC file contains DIRECT for non-AI domains (fallback)
- Custom PAC rules from admin API are included
- PAC file regeneration respects cache headers
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from anonreq.discovery.hostname_matcher import HostnameMatcher
from anonreq.discovery.hostname_signatures import AI_SIGNATURES, ProviderSignature


# ---------------------------------------------------------------------------
# PACGenerator unit tests
# ---------------------------------------------------------------------------


class TestPACGenerator:
    """Unit tests for PACGenerator."""

    def test_generate_returns_string(self):
        """PAC output is a non-empty string."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator(
            [".openai.com", ".anthropic.com", ".googleapis.com"],
            "proxy.anonreq.local",
            8080,
        )
        pac = gen.generate()
        assert isinstance(pac, str)
        assert len(pac) > 0

    def test_pac_contains_findproxyforurl(self):
        """PAC file contains the FindProxyForURL function."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator(
            [".openai.com", ".anthropic.com", ".googleapis.com"],
            "proxy.anonreq.local",
            8080,
        )
        pac = gen.generate()
        assert "FindProxyForURL" in pac
        assert "url" in pac
        assert "host" in pac

    def test_pac_contains_proxy_directive(self):
        """PAC file includes PROXY directive for provider domains."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator(
            [".openai.com", ".anthropic.com", ".googleapis.com"],
            "proxy.anonreq.local",
            8080,
        )
        pac = gen.generate()
        assert "PROXY proxy.anonreq.local:8080" in pac

    def test_pac_contains_direct_fallback(self):
        """PAC file returns DIRECT as default fallback."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator(
            [".openai.com"], "proxy.anonreq.local", 8080,
        )
        pac = gen.generate()
        assert 'return "DIRECT"' in pac or 'return "DIRECT";' in pac

    def test_pac_uses_dnsdomainis(self):
        """PAC file uses dnsDomainIs or shExpMatch for domain matching."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator(
            [".openai.com", ".anthropic.com"], "proxy.anonreq.local", 8080,
        )
        pac = gen.generate()
        assert "dnsDomainIs" in pac or "shExpMatch" in pac

    def test_pac_includes_all_providers(self):
        """All provider domains are listed in the PAC file."""
        from anonreq.proxy.pac import PACGenerator

        domains = [".openai.com", ".anthropic.com", ".googleapis.com", ".mistral.ai"]
        gen = PACGenerator(domains, "proxy.anonreq.local", 8080)
        pac = gen.generate()
        for domain in domains:
            # Each domain should appear somewhere (without the leading dot for dnsDomainIs)
            assert domain.lstrip(".") in pac or domain in pac

    def test_custom_rule_added(self):
        """Custom PAC rules are added and reflected in generated PAC."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator([], "proxy.anonreq.local", 8080)
        gen.add_custom_rule("*.custom-ai.com", "PROXY other.proxy:3128")
        pac = gen.generate()
        assert "custom-ai.com" in pac
        assert "other.proxy:3128" in pac

    def test_custom_rule_removed(self):
        """Custom PAC rules can be removed."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator([], "proxy.anonreq.local", 8080)
        gen.add_custom_rule("*.custom-ai.com", "PROXY other.proxy:3128")
        gen.remove_custom_rule("*.custom-ai.com")
        pac = gen.generate()
        assert "custom-ai.com" not in pac

    def test_get_custom_rules(self):
        """Custom rules are returned as a list of dicts."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator([], "proxy.anonreq.local", 8080)
        gen.add_custom_rule("*.test.com", "PROXY test:8080")
        rules = gen.get_custom_rules()
        assert len(rules) == 1
        assert rules[0]["domain_pattern"] == "*.test.com"
        assert rules[0]["proxy"] == "PROXY test:8080"

    def test_pac_regenerates_after_rule_change(self):
        """PAC is regenerated when custom rules change."""
        from anonreq.proxy.pac import PACGenerator

        gen = PACGenerator([], "proxy.anonreq.local", 8080)
        pac1 = gen.generate()
        gen.add_custom_rule("*.new-ai.com", "PROXY new:8080")
        pac2 = gen.generate()
        assert pac2 != pac1
        assert "new-ai.com" in pac2

    def test_get_all_proxy_domains(self):
        """get_all_proxy_domains returns all known provider domains."""
        from anonreq.proxy.pac import PACGenerator

        domains = [".openai.com", ".anthropic.com"]
        gen = PACGenerator(domains, "proxy.anonreq.local", 8080)
        result = gen.get_all_proxy_domains()
        assert set(result) == set(domains)

    @pytest.mark.skip(reason="HostnameAllowlist created in Task 2")
    def test_integration_with_hostname_allowlist(self):
        """PACGenerator works with HostnameAllowlist.get_all_proxy_domains()."""
        from anonreq.discovery.hostname_allowlist import HostnameAllowlist
        from anonreq.proxy.pac import PACGenerator

        wl = HostnameAllowlist()
        domains = wl.get_all_proxy_domains()
        assert len(domains) > 0

        gen = PACGenerator(domains, "proxy.anonreq.local", 8080)
        pac = gen.generate()
        assert "PROXY proxy.anonreq.local:8080" in pac


# ---------------------------------------------------------------------------
# FastAPI route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pac_test_app():
    """Create a FastAPI app with the PAC router registered."""
    from anonreq.proxy.pac import router as pac_router

    app = FastAPI()
    app.include_router(pac_router)
    return app


@pytest.fixture
def pac_test_client(pac_test_app):
    """Test client for PAC route tests."""
    return TestClient(pac_test_app)


class TestPACRoutes:
    """Test suite for PAC HTTP routes."""

    def test_get_proxy_pac_returns_200(self, pac_test_client):
        """GET /v1/proxy.pac returns 200 OK."""
        response = pac_test_client.get("/v1/proxy.pac")
        assert response.status_code == 200

    def test_get_proxy_pac_content_type(self, pac_test_client):
        """GET /v1/proxy.pac returns application/x-ns-proxy-autoconfig."""
        response = pac_test_client.get("/v1/proxy.pac")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "application/x-ns-proxy-autoconfig" in content_type

    def test_get_proxy_pac_body(self, pac_test_client):
        """GET /v1/proxy.pac returns valid PAC JavaScript."""
        response = pac_test_client.get("/v1/proxy.pac")
        assert response.status_code == 200
        body = response.text
        assert "FindProxyForURL" in body
        assert "DIRECT" in body

    def test_get_proxy_pac_cache_header(self, pac_test_client):
        """GET /v1/proxy.pac includes Cache-Control header."""
        response = pac_test_client.get("/v1/proxy.pac")
        assert response.status_code == 200
        assert "cache-control" in response.headers

    def test_get_custom_rules_requires_auth(self, pac_test_client):
        """GET /v1/admin/proxy/pac/custom-rules returns 401 without auth."""
        response = pac_test_client.get("/v1/admin/proxy/pac/custom-rules")
        assert response.status_code in (401, 403)

    def test_post_custom_rules_requires_auth(self, pac_test_client):
        """POST /v1/admin/proxy/pac/custom-rules returns 401 without auth."""
        response = pac_test_client.post(
            "/v1/admin/proxy/pac/custom-rules",
            json={"domain_pattern": "*.test.com", "proxy": "PROXY test:8080"},
        )
        assert response.status_code in (401, 403)
