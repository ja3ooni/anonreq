"""Route table and reverse proxy routing for AI traffic.

Provides:
- ``RouteTable`` — hostname-to-provider mapping with reverse proxy URL
  resolution and dynamic route management.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RouteEntry:
    hostname: str
    provider: str
    target_url: str
    port: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteMatch:
    provider: str
    entry: RouteEntry
    matched_pattern: str


# Default route table: known AI provider hostnames → target URLs
DEFAULT_ROUTES: list[dict[str, Any]] = [
    {"hostname": "api.openai.com", "provider": "openai", "target_url": "https://api.openai.com"},
    {"hostname": "*.openai.com", "provider": "openai", "target_url": "https://api.openai.com"},
    {"hostname": "api.anthropic.com", "provider": "anthropic", "target_url": "https://api.anthropic.com"},
    {"hostname": "generativelanguage.googleapis.com", "provider": "gemini", "target_url": "https://generativelanguage.googleapis.com"},
    {"hostname": "localhost", "provider": "ollama", "target_url": "http://localhost:11434", "port": 11434},  # noqa: E501
    {"hostname": "127.0.0.1", "provider": "ollama", "target_url": "http://127.0.0.1:11434", "port": 11434},  # noqa: E501
    {"hostname": "api.deepseek.com", "provider": "deepseek", "target_url": "https://api.deepseek.com"},
    {"hostname": "api.mistral.ai", "provider": "mistral", "target_url": "https://api.mistral.ai"},
    {"hostname": "api.cohere.ai", "provider": "cohere", "target_url": "https://api.cohere.ai"},
    {"hostname": "api.together.xyz", "provider": "together", "target_url": "https://api.together.xyz"},
    {"hostname": "api.perplexity.ai", "provider": "perplexity", "target_url": "https://api.perplexity.ai"},
]


class RouteTable:
    """Maps hostnames to AI providers with reverse proxy URL resolution.

    Supports:
    - Default route entries for all known AI providers
    - Wildcard hostname patterns (e.g., ``*.openai.com``)
    - Dynamic add/remove/list operations at runtime
    - Provider URL resolution for reverse proxy forwarding
    """

    def __init__(self) -> None:
        self._entries: list[RouteEntry] = []
        self._wildcard_patterns: list[tuple[re.Pattern[str], RouteEntry]] = []
        self._load_defaults()

    def _load_defaults(self) -> None:
        for route_def in DEFAULT_ROUTES:
            entry = RouteEntry(
                hostname=route_def["hostname"],
                provider=route_def["provider"],
                target_url=route_def["target_url"],
                port=route_def.get("port"),
            )
            self._entries.append(entry)
            if entry.hostname.startswith("*."):
                pattern_str = re.escape(entry.hostname[2:])
                self._wildcard_patterns.append(
                    (re.compile(f"(^|\\.){pattern_str}$", re.IGNORECASE), entry)
                )

    def lookup(self, hostname: str) -> RouteMatch | None:
        """Look up a hostname and return a ``RouteMatch`` if found.

        Checks exact matches first, then wildcard patterns. Matching is
        case-insensitive.
        """
        hostname = hostname.strip()

        parts = hostname.rsplit(":", 1)
        lookup_host = parts[0]
        has_port = len(parts) > 1 and parts[1].isdigit()

        for entry in self._entries:
            if entry.hostname.startswith("*."):
                continue
            if lookup_host.lower() == entry.hostname.lower():
                return RouteMatch(
                    provider=entry.provider,
                    entry=entry,
                    matched_pattern=entry.hostname,
                )

        for pattern, entry in self._wildcard_patterns:
            if pattern.search(lookup_host):
                return RouteMatch(
                    provider=entry.provider,
                    entry=entry,
                    matched_pattern=entry.hostname,
                )

        if has_port:
            for entry in self._entries:
                if entry.port is not None and str(entry.port) == parts[1]:
                    return RouteMatch(
                        provider=entry.provider,
                        entry=entry,
                        matched_pattern=entry.hostname,
                    )

        return None

    def add_route(
        self,
        hostname: str,
        provider: str,
        target_url: str,
        port: int | None = None,
    ) -> RouteEntry:
        """Add or override a route entry.

        If a route with the same hostname already exists, it is replaced.
        """
        self.remove_route(hostname)

        entry = RouteEntry(
            hostname=hostname,
            provider=provider,
            target_url=target_url,
            port=port,
        )
        self._entries.append(entry)

        if entry.hostname.startswith("*."):
            pattern_str = re.escape(entry.hostname[2:])
            self._wildcard_patterns.append(
                (re.compile(f"(^|\\.){pattern_str}$", re.IGNORECASE), entry)
            )

        return entry

    def remove_route(self, hostname: str) -> None:
        """Remove a route by hostname. No-op if not found."""
        self._entries = [e for e in self._entries if e.hostname != hostname]
        self._wildcard_patterns = [
            (p, e) for p, e in self._wildcard_patterns if e.hostname != hostname
        ]

    def list_routes(self) -> list[RouteEntry]:
        """Return a copy of all route entries."""
        return list(self._entries)

    def resolve_provider_url(self, provider: str, path: str) -> str | None:
        """Resolve a provider's base URL with the given path.

        Returns the full URL string (e.g., ``https://api.openai.com/v1/chat/completions``)
        or ``None`` if the provider has no route.
        """
        for entry in self._entries:
            if entry.provider == provider:
                base = entry.target_url.rstrip("/")
                request_path = path if path.startswith("/") else f"/{path}"
                return f"{base}{request_path}"
        return None
