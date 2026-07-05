"""PAC file generation for the Universal AI Traffic Gateway.

Per D-007, D-009:
- ``PACGenerator`` produces Netscape PAC (proxy auto-config) JavaScript files
  that route known AI provider traffic through the gateway proxy.
- ``router`` exposes ``GET /v1/proxy.pac`` and admin custom-rules endpoints.
- Custom rules allow administrators to override PAC routing for specific
  domain patterns.

The generated PAC file uses ``dnsDomainIs`` for explicit domain matching
and falls back to ``DIRECT`` for non-AI traffic.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from anonreq.admin.auth import verify_admin_api_key

logger = structlog.get_logger()

__all__ = [
    "PACGenerator",
    "router",
    "CustomRuleRequest",
]


class CustomRuleRequest(BaseModel):
    """Request body for adding a custom PAC rule.

    Attributes:
        domain_pattern: Domain pattern to match (e.g. ``*.example.com``).
        proxy: Proxy directive (e.g. ``PROXY proxy.host:8080``).
    """

    domain_pattern: str
    proxy: str


class _CustomRule:
    """Internal representation of a custom PAC rule."""

    __slots__ = ("domain_pattern", "proxy")

    def __init__(self, domain_pattern: str, proxy: str) -> None:
        self.domain_pattern = domain_pattern
        self.proxy = proxy

    def to_dict(self) -> dict[str, str]:
        return {
            "domain_pattern": self.domain_pattern,
            "proxy": self.proxy,
        }


class PACGenerator:
    """Generates Netscape PAC (proxy auto-config) files.

    The generator produces JavaScript PAC files that route traffic for known
    AI provider domains through a specified proxy, while allowing all other
    traffic to go direct. Custom rules can override the default mappings.

    Args:
        allowlist: List of domain patterns (e.g. ``.openai.com``) or a
            ``HostnameAllowlist`` instance whose ``get_all_proxy_domains()``
            method provides the domain list.
        gateway_host: Hostname of the gateway proxy.
        gateway_port: Port of the gateway proxy.
    """

    def __init__(
        self,
        allowlist: list[str] | Any,
        gateway_host: str,
        gateway_port: int,
    ) -> None:
        self._gateway_host = gateway_host
        self._gateway_port = gateway_port

        # Resolve allowlist — accept list[str] or HostnameAllowlist-like object
        if isinstance(allowlist, list):
            self._domains: list[str] = list(allowlist)
        else:
            try:
                self._domains = list(allowlist.get_all_proxy_domains())
            except (AttributeError, TypeError):
                self._domains = []

        self._custom_rules: list[_CustomRule] = []
        self._cached_pac: str | None = None
        self._cache_hash: str | None = None

    def _compute_hash(self) -> str:
        """Compute a hash of current state for cache invalidation."""
        raw = (
            str(self._domains)
            + str([(r.domain_pattern, r.proxy) for r in self._custom_rules])
            + self._gateway_host
            + str(self._gateway_port)
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _generate_pac_js(self) -> str:
        """Generate the PAC JavaScript source.

        Returns:
            Complete PAC file content as a string.
        """
        proxy = f"PROXY {self._gateway_host}:{self._gateway_port}"

        lines: list[str] = [
            "function FindProxyForURL(url, host) {",
        ]

        # Add custom rules first (they take priority)
        for rule in self._custom_rules:
            pattern = rule.domain_pattern
            if pattern.startswith("*."):
                # Wildcard subdomain pattern: *.example.com
                domain = pattern[2:]
                lines.append(
                    f'    if (dnsDomainIs(host, ".{domain}"))'
                    f' return "{rule.proxy}";'
                )
            else:
                # Exact domain
                lines.append(
                    f'    if (dnsDomainIs(host, "{pattern}"))'
                    f' return "{rule.proxy}";'
                )

        # Add provider domains from allowlist
        for domain in self._domains:
            clean = domain.lstrip(".")
            lines.append(
                f'    if (dnsDomainIs(host, ".{clean}"))'
                f' return "{proxy}";'
            )

        # Default fallback: DIRECT
        lines.append('    return "DIRECT";')
        lines.append("}")

        return "\n".join(lines) + "\n"

    def generate(self) -> str:
        """Generate (or return cached) PAC file content.

        Returns:
            PAC JavaScript content as a string.
        """
        current_hash = self._compute_hash()
        if self._cached_pac is not None and self._cache_hash == current_hash:
            return self._cached_pac

        self._cached_pac = self._generate_pac_js()
        self._cache_hash = current_hash
        return self._cached_pac

    def add_custom_rule(self, domain_pattern: str, proxy: str) -> None:
        """Add a custom PAC rule.

        If a rule with the same domain pattern already exists, it is
        replaced with the new proxy directive. Invalidates the PAC cache.

        Args:
            domain_pattern: Domain pattern to match (e.g. ``*.example.com``).
            proxy: Proxy directive (e.g. ``PROXY proxy.host:8080``).
        """
        # Replace existing rule with same pattern
        for i, rule in enumerate(self._custom_rules):
            if rule.domain_pattern == domain_pattern:
                self._custom_rules[i] = _CustomRule(domain_pattern, proxy)
                self._cached_pac = None
                return

        self._custom_rules.append(_CustomRule(domain_pattern, proxy))
        self._cached_pac = None

    def remove_custom_rule(self, domain_pattern: str) -> None:
        """Remove a custom PAC rule by domain pattern.

        Args:
            domain_pattern: The domain pattern of the rule to remove.
        """
        self._custom_rules = [
            r for r in self._custom_rules if r.domain_pattern != domain_pattern
        ]
        self._cached_pac = None

    def get_custom_rules(self) -> list[dict[str, str]]:
        """Return all custom PAC rules.

        Returns:
            List of dicts with ``domain_pattern`` and ``proxy`` keys.
        """
        return [r.to_dict() for r in self._custom_rules]

    def get_all_proxy_domains(self) -> list[str]:
        """Return all known AI provider domains.

        Returns:
            List of domain pattern strings.
        """
        return list(self._domains)


# ---------------------------------------------------------------------------
# FastAPI router — serves PAC file and admin endpoints
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1")
"""FastAPI router for proxy.pac and admin custom-rules endpoints.

Routes:
    - ``GET /proxy.pac`` — Returns the PAC file (public, no auth).
    - ``GET /admin/proxy/pac/custom-rules`` — Lists custom rules (admin auth).
    - ``POST /admin/proxy/pac/custom-rules`` — Adds a custom rule (admin auth).
"""

# Module-level generator singleton — initialised lazily
_generator: PACGenerator | None = None


def _get_generator(request: Request) -> PACGenerator:
    """Get or create the PACGenerator from app state.

    Uses app state to allow the generator to be shared across requests
    and configured during app startup.
    """
    global _generator  # noqa: PLW0603

    gen: PACGenerator | None = getattr(request.app.state, "pac_generator", None)
    if gen is not None:
        return gen

    if _generator is not None:
        return _generator

    # Fallback: create a minimal generator
    _generator = PACGenerator(
        [".openai.com", ".anthropic.com", ".googleapis.com"],
        "localhost",
        8080,
    )
    return _generator


@router.get("/proxy.pac")
async def get_proxy_pac(request: Request) -> Response:
    """Serve the PAC file.

    Returns the generated Netscape PAC JavaScript with
    ``Content-Type: application/x-ns-proxy-autoconfig`` and
    ``Cache-Control: max-age=3600``.

    No authentication required — PAC files are public configuration.
    """
    gen = _get_generator(request)
    pac_content = gen.generate()
    return Response(
        content=pac_content,
        media_type="application/x-ns-proxy-autoconfig",
        headers={
            "Cache-Control": "max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/admin/proxy/pac/custom-rules")
async def get_custom_rules(
    request: Request,
    _auth: bool = Depends(verify_admin_api_key),
) -> list[dict[str, str]]:
    """Return all custom PAC rules.

    Requires admin authentication via ``verify_admin_api_key``.
    """
    gen = _get_generator(request)
    return gen.get_custom_rules()


@router.post("/admin/proxy/pac/custom-rules")
async def add_custom_rule(
    rule: CustomRuleRequest,
    request: Request,
    _auth: bool = Depends(verify_admin_api_key),
) -> dict[str, str]:
    """Add a custom PAC rule.

    Requires admin authentication. The rule is added to the PAC generator
    and will be reflected in the next PAC file generation.

    Args:
        rule: The custom rule to add.

    Returns:
        A status message confirming the rule was added.
    """
    gen = _get_generator(request)
    gen.add_custom_rule(rule.domain_pattern, rule.proxy)
    logger.info(
        "Custom PAC rule added",
        domain_pattern=rule.domain_pattern,
        proxy=rule.proxy,
    )
    return {"status": "ok", "domain_pattern": rule.domain_pattern}
