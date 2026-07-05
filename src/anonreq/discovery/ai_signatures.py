"""AI provider signature database — single source of truth for provider identification.

Provides a curated list of 20+ AI provider signatures with hostname patterns,
IP CIDR ranges, API endpoint paths, tier classification, jurisdiction, and
certifications. Helper functions for matching hostnames, IPs, and paths.

Per D-002, D-007, D-010:
- 20+ providers covering major US, regional EU/CN, and self-hosted platforms
- Wildcard hostname matching via fnmatch
- CIDR IP range matching via ipaddress
- Path-based matching for AI API endpoints
- Signatures are code (Python module), not YAML
"""

from __future__ import annotations

import fnmatch
import ipaddress
from typing import Any

# ---------------------------------------------------------------------------
# AI provider signature database — 20+ providers
# ---------------------------------------------------------------------------

AI_PROVIDER_SIGNATURES: list[dict[str, Any]] = [
    # ===== Major US providers =====
    {
        "provider": "openai",
        "hostnames": [
            "api.openai.com",
            "*.openai.com",
            "oaksvc.openai.com",
            "*.oaksvc.openai.com",
        ],
        "ip_ranges": ["104.18.0.0/16", "172.64.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/embeddings",
            "/v1/moderations",
            "/v1/models",
            "/v1/images/generations",
            "/v1/audio/transcriptions",
            "/v1/audio/translations",
            "/v1/files",
            "/v1/fine-tunes",
            "/v1/assistants",
            "/v1/threads",
            "/v1/threads/",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": ["soc2", "iso27001"],
    },
    {
        "provider": "anthropic",
        "hostnames": [
            "api.anthropic.com",
            "*.anthropic.com",
        ],
        "ip_ranges": ["104.18.0.0/16", "172.64.0.0/16"],
        "paths": [
            "/v1/messages",
            "/v1/complete",
            "/v1/chat/completions",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "gemini",
        "hostnames": [
            "generativelanguage.googleapis.com",
            "*.googleapis.com",
            "ai.google.dev",
        ],
        "ip_ranges": ["142.250.0.0/16", "172.217.0.0/16"],
        "paths": [
            "/v1/models",
            "/v1beta/models",
            "/v1/models/",
            "/v1beta/models/",
            "/v1/chat/completions",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": ["soc2", "iso27001"],
    },
    {
        "provider": "bedrock",
        "hostnames": [
            "bedrock-runtime.*.amazonaws.com",
            "*.bedrock.aws",
            "bedrock.*.amazonaws.com",
        ],
        "ip_ranges": ["52.94.0.0/16", "54.239.0.0/16"],
        "paths": [
            "/model/",
            "/invoke",
            "/invoke-with-response-stream",
            "/converse",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": ["soc2", "iso27001"],
    },
    {
        "provider": "azure_openai",
        "hostnames": [
            "*.openai.azure.com",
            "*.cognitiveservices.azure.com",
            "*.api.cognitive.microsoft.com",
        ],
        "ip_ranges": ["40.84.0.0/16", "52.170.0.0/16"],
        "paths": [
            "/openai/deployments/",
            "/chat/completions",
            "/completions",
            "/embeddings",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": ["soc2", "iso27001"],
    },
    {
        "provider": "meta_llama",
        "hostnames": [
            "api.meta.ai",
            "*.meta.ai",
            "llama.meta.com",
            "*.llama.meta.com",
            "api.llama.ai",
            "*.llama.ai",
        ],
        "ip_ranges": ["31.13.0.0/16", "157.240.0.0/16"],
        "paths": [
            "/api/v1/chat",
            "/api/v1/completions",
        ],
        "tier": "major",
        "jurisdiction": "us",
        "certifications": [],
    },
    # ===== Regional US providers =====
    {
        "provider": "mistral",
        "hostnames": [
            "api.mistral.ai",
            "*.mistral.ai",
        ],
        "ip_ranges": ["51.158.0.0/16", "163.172.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/embeddings",
            "/v1/models",
        ],
        "tier": "regional",
        "jurisdiction": "eu",
        "certifications": ["soc2"],
    },
    {
        "provider": "cohere",
        "hostnames": [
            "api.cohere.ai",
            "*.cohere.ai",
            "api.cohere.com",
            "*.cohere.com",
        ],
        "ip_ranges": ["34.64.0.0/16", "35.184.0.0/16"],
        "paths": [
            "/v1/generate",
            "/v1/embed",
            "/v1/classify",
            "/v1/rerank",
            "/v1/chat",
            "/v1/summarize",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "groq",
        "hostnames": [
            "api.groq.com",
            "*.groq.com",
        ],
        "ip_ranges": ["146.75.0.0/16"],
        "paths": [
            "/openai/v1/chat/completions",
            "/openai/v1/models",
            "/v1/chat/completions",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "together",
        "hostnames": [
            "api.together.xyz",
            "*.together.xyz",
        ],
        "ip_ranges": ["104.26.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/embeddings",
            "/v1/models",
            "/inference",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": [],
    },
    {
        "provider": "perplexity",
        "hostnames": [
            "api.perplexity.ai",
            "*.perplexity.ai",
            "pplx.ai",
            "*.pplx.ai",
        ],
        "ip_ranges": ["104.18.0.0/16"],
        "paths": [
            "/chat/completions",
            "/v1/chat/completions",
            "/v1/models",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "deepseek",
        "hostnames": [
            "api.deepseek.com",
            "*.deepseek.com",
        ],
        "ip_ranges": ["47.88.0.0/16", "8.210.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
        ],
        "tier": "regional",
        "jurisdiction": "cn",
        "certifications": [],
    },
    {
        "provider": "xai",
        "hostnames": [
            "api.x.ai",
            "*.x.ai",
            "api.grok.x",
            "*.grok.x",
        ],
        "ip_ranges": ["104.18.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": [],
    },
    {
        "provider": "fireworks",
        "hostnames": [
            "api.fireworks.ai",
            "*.fireworks.ai",
        ],
        "ip_ranges": ["34.96.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
            "/inference",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": [],
    },
    {
        "provider": "replicate",
        "hostnames": [
            "api.replicate.com",
            "*.replicate.com",
            "replicate.delivery",
            "*.replicate.delivery",
        ],
        "ip_ranges": ["34.120.0.0/16"],
        "paths": [
            "/v1/models",
            "/v1/predictions",
            "/v1/trainings",
            "/v1/collections",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "huggingface",
        "hostnames": [
            "api-inference.huggingface.co",
            "*.huggingface.co",
        ],
        "ip_ranges": ["34.73.0.0/16", "35.190.0.0/16"],
        "paths": [
            "/models/",
            "/v1/chat/completions",
            "/pipeline/",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": ["soc2"],
    },
    {
        "provider": "alibaba_cloud",
        "hostnames": [
            "dashscope.aliyuncs.com",
            "*.aliyuncs.com",
            "*.tongyi.aliyun.com",
        ],
        "ip_ranges": ["47.74.0.0/16", "8.129.0.0/16"],
        "paths": [
            "/api/v1/services/aigc/text-generation/generation",
            "/api/v1/chat/completions",
        ],
        "tier": "regional",
        "jurisdiction": "cn",
        "certifications": ["iso27001"],
    },
    # ===== Additional regional/self-hosted providers =====
    {
        "provider": "ollama",
        "hostnames": [
            "localhost",
            "127.0.0.1",
            "ollama",
            "*.ollama.ai",
            "ollama.ai",
        ],
        "ip_ranges": [],
        "paths": [
            "/api/chat",
            "/api/generate",
            "/api/embeddings",
            "/api/tags",
        ],
        "tier": "regional",
        "jurisdiction": "other",
        "certifications": [],
    },
    {
        "provider": "vllm",
        "hostnames": [
            "*.vllm",
            "vllm",
        ],
        "ip_ranges": [],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
            "/health",
        ],
        "tier": "regional",
        "jurisdiction": "other",
        "certifications": [],
    },
    {
        "provider": "lm_studio",
        "hostnames": [
            "localhost:1234",
            "127.0.0.1:1234",
        ],
        "ip_ranges": [],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
            "/v1/embeddings",
        ],
        "tier": "regional",
        "jurisdiction": "other",
        "certifications": [],
    },
    {
        "provider": "togetherai",
        "hostnames": [
            "api.together.ai",
            "*.together.ai",
        ],
        "ip_ranges": ["104.26.0.0/16"],
        "paths": [
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/models",
        ],
        "tier": "regional",
        "jurisdiction": "us",
        "certifications": [],
    },
]


def _match_wildcard(hostname: str, pattern: str) -> bool:
    """Match a hostname against a wildcard pattern.

    Supports patterns with ``*`` wildcards.  Pattern ``*.openai.com`` matches
    ``api.openai.com`` but not ``openai.com``.
    """
    return fnmatch.fnmatch(hostname.lower(), pattern.lower())


def get_provider_by_hostname(hostname: str) -> dict[str, Any] | None:
    """Find the first AI provider signature matching the given hostname.

    Tries exact match first, then wildcard matching. Returns the first
    match found (exact matches preferred by ordering).

    Args:
        hostname: The hostname to look up (e.g. ``api.openai.com``).

    Returns:
        The matching provider signature dict, or ``None``.
    """
    hostname = hostname.lower()

    # Exact match first
    for sig in AI_PROVIDER_SIGNATURES:
        for pattern in sig["hostnames"]:
            # Handle wildcard patterns: for exact match, strip leading *. and compare remainder
            clean_pattern = pattern.lower().replace("*.", "")
            if hostname == clean_pattern:
                return sig

    # Wildcard match
    for sig in AI_PROVIDER_SIGNATURES:
        for pattern in sig["hostnames"]:
            if "*" in pattern and _match_wildcard(hostname, pattern):
                return sig

    return None


def get_provider_by_ip(ip_str: str) -> dict[str, Any] | None:
    """Find a provider signature matching the given IP address.

    Matches against each provider's ``ip_ranges`` CIDR list.

    Args:
        ip_str: The IP address as a string (e.g. ``104.18.1.1``).

    Returns:
        The matching provider signature dict, or ``None``.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None

    for sig in AI_PROVIDER_SIGNATURES:
        for cidr in sig.get("ip_ranges", []):
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if addr in network:
                    return sig
            except ValueError:
                continue

    return None


def get_provider_by_path(path: str) -> dict[str, Any] | None:
    """Find provider signatures matching the given URL path.

    Matches if the path starts with any of the provider's known API paths.

    Args:
        path: The URL path to check (e.g. ``/v1/chat/completions``).

    Returns:
        The matching provider signature dict, or ``None``.
    """
    path_lower = path.lower()

    for sig in AI_PROVIDER_SIGNATURES:
        for api_path in sig.get("paths", []):
            if path_lower.startswith(api_path.lower()):
                return sig

    return None
