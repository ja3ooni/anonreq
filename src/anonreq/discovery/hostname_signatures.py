"""AI provider hostname/IP signature database.

Provides a curated database of known AI provider hostnames and IP ranges
for detecting AI service usage from DNS and proxy logs.

Per D-002:
- Covers 15+ AI providers with hostnames (wildcard) and IP ranges (CIDR)
- Supports exact, wildcard, multi-level domain, and CIDR IP matching
- Runtime custom provider registration via add_custom_signature
"""

from __future__ import annotations

import fnmatch
import ipaddress


class ProviderSignature:
    """Signature for a single AI provider.

    Attributes:
        provider: Provider name (e.g., "openai", "anthropic").
        hostnames: List of hostname patterns (supports * wildcard).
        ip_ranges: List of CIDR IP ranges.
        tier: Provider tier — "major", "regional", or "unknown".
        jurisdiction: Data jurisdiction — "us", "eu", "cn", or "other".
    """

    __slots__ = ("hostnames", "ip_ranges", "jurisdiction", "provider", "tier")

    def __init__(
        self,
        provider: str,
        hostnames: list[str],
        ip_ranges: list[str] | None = None,
        tier: str = "unknown",
        jurisdiction: str = "other",
    ) -> None:
        self.provider = provider
        self.hostnames = hostnames
        self.ip_ranges = ip_ranges if ip_ranges else []
        self.tier = tier
        self.jurisdiction = jurisdiction

    def __repr__(self) -> str:
        return f"ProviderSignature(provider={self.provider!r}, tier={self.tier!r})"


# ---------------------------------------------------------------------------
# AI provider signatures — curated database
# ---------------------------------------------------------------------------

AI_SIGNATURES: list[ProviderSignature] = [
    # Major US providers
    ProviderSignature(
        "openai",
        ["api.openai.com", "*.openai.com", "oaksvc.openai.com", "*.oaksvc.openai.com"],
        ["104.18.0.0/16", "172.64.0.0/16"],
        "major",
        "us",
    ),
    ProviderSignature(
        "anthropic",
        ["api.anthropic.com", "*.anthropic.com"],
        ["104.18.0.0/16", "172.64.0.0/16"],
        "major",
        "us",
    ),
    ProviderSignature(
        "gemini",
        ["generativelanguage.googleapis.com", "*.googleapis.com", "ai.google.dev"],
        ["142.250.0.0/16", "172.217.0.0/16"],
        "major",
        "us",
    ),
    ProviderSignature(
        "bedrock",
        ["bedrock-runtime.*.amazonaws.com", "*.bedrock.aws", "bedrock.*.amazonaws.com"],
        ["52.94.0.0/16", "54.239.0.0/16"],
        "major",
        "us",
    ),
    ProviderSignature(
        "azure_openai",
        ["*.openai.azure.com", "*.cognitiveservices.azure.com", "*.api.cognitive.microsoft.com"],
        ["40.84.0.0/16", "52.170.0.0/16"],
        "major",
        "us",
    ),
    ProviderSignature(
        "meta_llama",
        ["api.meta.ai", "*.meta.ai", "llama.meta.com", "*.llama.meta.com"],
        ["31.13.0.0/16", "157.240.0.0/16"],
        "major",
        "us",
    ),
    # Regional providers
    ProviderSignature(
        "mistral",
        ["api.mistral.ai", "*.mistral.ai"],
        ["51.158.0.0/16", "163.172.0.0/16"],
        "regional",
        "eu",
    ),
    ProviderSignature(
        "cohere",
        ["api.cohere.ai", "*.cohere.ai", "api.cohere.com", "*.cohere.com"],
        ["34.64.0.0/16", "35.184.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "groq",
        ["api.groq.com", "*.groq.com"],
        ["146.75.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "together",
        ["api.together.xyz", "*.together.xyz"],
        ["104.26.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "perplexity",
        ["api.perplexity.ai", "*.perplexity.ai", "pplx.ai", "*.pplx.ai"],
        ["104.18.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "deepseek",
        ["api.deepseek.com", "*.deepseek.com"],
        ["47.88.0.0/16", "8.210.0.0/16"],
        "regional",
        "cn",
    ),
    ProviderSignature(
        "claude",
        ["api.anthropic.com", "*.anthropic.com"],
        [],  # shares infra with anthropic
        "regional",
        "us",
    ),
    ProviderSignature(
        "xai",
        ["api.x.ai", "*.x.ai", "api.grok.x", "*.grok.x"],
        ["104.18.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "fireworks",
        ["api.fireworks.ai", "*.fireworks.ai"],
        ["34.96.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "replicate",
        ["api.replicate.com", "*.replicate.com", "replicate.delivery", "*.replicate.delivery"],
        ["34.120.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "huggingface",
        ["api-inference.huggingface.co", "*.huggingface.co"],
        ["34.73.0.0/16", "35.190.0.0/16"],
        "regional",
        "us",
    ),
    ProviderSignature(
        "alibaba_cloud",
        ["dashscope.aliyuncs.com", "*.aliyuncs.com", "*.tongyi.aliyun.com"],
        ["47.74.0.0/16", "8.129.0.0/16"],
        "regional",
        "cn",
    ),
]


def _match_wildcard(hostname: str, pattern: str) -> bool:
    """Match a hostname against a wildcard pattern using fnmatch."""
    return fnmatch.fnmatch(hostname.lower(), pattern.lower())


def get_signature_by_hostname(hostname: str) -> ProviderSignature | None:
    """Find a provider signature matching the given hostname.

    Performs a linear scan with exact match first, then wildcard matching.
    Returns the first match found (highest confidence = exact match preferred).
    """
    hostname = hostname.lower()

    for sig in AI_SIGNATURES:
        for pattern in sig.hostnames:
            if hostname == pattern.lower().replace("*.", ""):
                return sig

    for sig in AI_SIGNATURES:
        for pattern in sig.hostnames:
            if _match_wildcard(hostname, pattern):
                return sig

    return None


def get_signature_by_ip(ip: str) -> ProviderSignature | None:
    """Find a provider signature matching the given IP via CIDR matching."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None

    for sig in AI_SIGNATURES:
        for cidr in sig.ip_ranges:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if addr in network:
                    return sig
            except ValueError:
                continue

    return None


def add_custom_signature(sig: ProviderSignature) -> None:
    """Register a custom provider signature at runtime."""
    AI_SIGNATURES.append(sig)
