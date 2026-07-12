"""Tests for the route table and reverse proxy routing."""

from __future__ import annotations

import pytest

from anonreq.gateway.router import RouteEntry, RouteTable


class TestRouteEntry:
    """Tests for RouteEntry data model."""

    def test_route_entry_creation(self):
        entry = RouteEntry(
            hostname="api.openai.com",
            provider="openai",
            target_url="https://api.openai.com",
        )
        assert entry.hostname == "api.openai.com"
        assert entry.provider == "openai"
        assert entry.target_url == "https://api.openai.com"

    def test_route_entry_with_port(self):
        entry = RouteEntry(
            hostname="localhost",
            provider="ollama",
            target_url="http://localhost:11434",
            port=11434,
        )
        assert entry.port == 11434


class TestRouteTable:
    """Tests for RouteTable — hostname → provider mapping."""

    @pytest.fixture
    def route_table(self):
        return RouteTable()

    def test_default_routes_loaded(self, route_table):
        routes = route_table.list_routes()
        assert len(routes) >= 4
        provider_names = [r.provider for r in routes]
        assert "openai" in provider_names
        assert "anthropic" in provider_names
        assert "gemini" in provider_names
        assert "ollama" in provider_names

    def test_lookup_openai(self, route_table):
        match = route_table.lookup("api.openai.com")
        assert match is not None
        assert match.provider == "openai"
        assert match.entry.hostname == "api.openai.com"

    def test_lookup_anthropic(self, route_table):
        match = route_table.lookup("api.anthropic.com")
        assert match is not None
        assert match.provider == "anthropic"

    def test_lookup_gemini(self, route_table):
        match = route_table.lookup("generativelanguage.googleapis.com")
        assert match is not None
        assert match.provider == "gemini"

    def test_lookup_ollama(self, route_table):
        match = route_table.lookup("localhost:11434")
        assert match is not None
        assert match.provider == "ollama"

    def test_lookup_unknown_hostname(self, route_table):
        match = route_table.lookup("unknown.example.com")
        assert match is None

    def test_lookup_with_wildcard(self, route_table):
        match = route_table.lookup("custom.openai.com")
        assert match is not None
        assert match.provider == "openai"

    def test_add_custom_route(self, route_table):
        route_table.add_route(
            hostname="my-llm.internal.company.com",
            provider="custom",
            target_url="https://my-llm.internal.company.com/v1",
        )
        match = route_table.lookup("my-llm.internal.company.com")
        assert match is not None
        assert match.provider == "custom"
        assert match.entry.target_url == "https://my-llm.internal.company.com/v1"

    def test_add_route_overrides_existing(self, route_table):
        route_table.add_route(
            hostname="api.openai.com",
            provider="custom-openai",
            target_url="https://custom-openai.internal/v1",
        )
        match = route_table.lookup("api.openai.com")
        assert match is not None
        assert match.provider == "custom-openai"
        assert match.entry.target_url == "https://custom-openai.internal/v1"

    def test_remove_route(self, route_table):
        route_table.add_route(
            hostname="test-route.ai",
            provider="test",
            target_url="https://test-route.ai",
        )
        assert route_table.lookup("test-route.ai") is not None
        route_table.remove_route("test-route.ai")
        assert route_table.lookup("test-route.ai") is None

    def test_remove_nonexistent_route(self, route_table):
        route_table.remove_route("nonexistent.ai")

    def test_lookup_case_insensitive(self, route_table):
        match = route_table.lookup("API.OpenAI.COM")
        assert match is not None
        assert match.provider == "openai"

    def test_list_routes_returns_copy(self, route_table):
        routes = route_table.list_routes()
        routes.clear()
        assert len(route_table.list_routes()) > 0

    def test_resolve_provider_url_openai(self, route_table):
        url = route_table.resolve_provider_url("openai", "/v1/chat/completions")
        assert url == "https://api.openai.com/v1/chat/completions"

    def test_resolve_provider_url_unknown(self, route_table):
        url = route_table.resolve_provider_url("nonexistent", "/v1/test")
        assert url is None

    def test_lookup_deepseek_default(self):
        rt = RouteTable()
        match = rt.lookup("api.deepseek.com")
        assert match is not None
        assert match.provider == "deepseek"
