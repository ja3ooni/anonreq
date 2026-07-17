"""AI traffic detection and MCP protocol inspection.

Provides:
- ``AIDetector`` — hostname and payload-pattern-based AI provider detection
- ``MCPInspector`` — Model Context Protocol (JSON-RPC) message parsing and
  tool-call extraction
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderMatch:
    provider: str
    confidence: float
    matched_on: str


@dataclass(frozen=True)
class TrafficClassification:
    is_ai_traffic: bool
    provider: str | None = None
    endpoint_type: str | None = None
    detected_by_hostname: bool = False
    confidence: float = 0.0


@dataclass(frozen=True)
class MCPMessage:
    jsonrpc: str
    method: str | None = None
    params: dict[str, Any] | None = None
    msg_id: int | str | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    @property
    def method_category(self) -> str | None:
        if self.method and "/" in self.method:
            return self.method.split("/")[0]
        return None

    @property
    def method_name(self) -> str | None:
        if self.method and "/" in self.method:
            return self.method.split("/", 1)[1]
        return None


# ---------------------------------------------------------------------------
# Known AI provider hostnames and model patterns
# ---------------------------------------------------------------------------

KNOWN_PROVIDERS: dict[str, list[re.Pattern]] = {
    "openai": [
        re.compile(r"(^|\.)api\.openai\.com$", re.IGNORECASE),
        re.compile(r"(^|\.)api\.openai\.com$", re.IGNORECASE),
        re.compile(r"(^|\.)oai\.azure\.com$", re.IGNORECASE),
    ],
    "anthropic": [
        re.compile(r"(^|\.)api\.anthropic\.com$", re.IGNORECASE),
    ],
    "gemini": [
        re.compile(r"(^|\.)generativelanguage\.googleapis\.com$", re.IGNORECASE),
    ],
    "ollama": [
        re.compile(r"^localhost(:\d+)?$", re.IGNORECASE),
        re.compile(r"^127\.0\.0\.1(:\d+)?$"),
    ],
    "deepseek": [
        re.compile(r"(^|\.)api\.deepseek\.com$", re.IGNORECASE),
    ],
    "mistral": [
        re.compile(r"(^|\.)api\.mistral\.ai$", re.IGNORECASE),
    ],
    "cohere": [
        re.compile(r"(^|\.)api\.cohere\.ai$", re.IGNORECASE),
    ],
    "together": [
        re.compile(r"(^|\.)api\.together\.xyz$", re.IGNORECASE),
    ],
    "perplexity": [
        re.compile(r"(^|\.)api\.perplexity\.ai$", re.IGNORECASE),
    ],
}

MODEL_TO_PROVIDER: dict[re.Pattern, str] = {
    re.compile(r"^gpt-", re.IGNORECASE): "openai",
    re.compile(r"^o[0-9]|^o1-|^o3-", re.IGNORECASE): "openai",
    re.compile(r"^claude-", re.IGNORECASE): "anthropic",
    re.compile(r"^gemini-", re.IGNORECASE): "gemini",
    re.compile(r"^deepseek-", re.IGNORECASE): "deepseek",
    re.compile(r"^mistral-", re.IGNORECASE): "mistral",
    re.compile(r"^command-", re.IGNORECASE): "cohere",
    re.compile(r"^mixtral-", re.IGNORECASE): "mistral",
}

AI_ENDPOINT_PATTERNS: list[re.Pattern] = [
    re.compile(r"/v1/chat/completions$", re.IGNORECASE),
    re.compile(r"/v1/completions$", re.IGNORECASE),
    re.compile(r"/v1/embeddings$", re.IGNORECASE),
    re.compile(r"/v1/messages$", re.IGNORECASE),
    re.compile(r"/v1/models$", re.IGNORECASE),
    re.compile(r"/v1/chat$", re.IGNORECASE),
    re.compile(r"/v1/generate$", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# AIDetector
# ---------------------------------------------------------------------------


class AIDetector:
    """Detect AI provider traffic by hostname, endpoint path, and payload.

    Supports:
    - Hostname-based detection against a known AI provider registry
    - Pattern-based detection from request bodies (model names, payload shape)
    - Custom provider pattern injection
    """

    def __init__(self, custom_patterns: dict[str, list[str]] | None = None) -> None:
        self._providers: dict[str, list[re.Pattern]] = {
            provider: list(patterns)
            for provider, patterns in KNOWN_PROVIDERS.items()
        }
        if custom_patterns:
            for provider, patterns in custom_patterns.items():
                compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
                if provider in self._providers:
                    self._providers[provider].extend(compiled)
                else:
                    self._providers[provider] = compiled

    def detect_hostname(self, hostname: str) -> ProviderMatch | None:
        """Match a hostname against known AI provider patterns.

        Returns ``ProviderMatch`` if the hostname matches a known provider,
        ``None`` otherwise.
        """
        for provider, patterns in self._providers.items():
            for pattern in patterns:
                if pattern.search(hostname.strip()):
                    return ProviderMatch(
                        provider=provider,
                        confidence=0.95,
                        matched_on="hostname",
                    )
        return None

    def match_model_to_provider(self, model: str) -> str | None:
        """Infer the AI provider from a model name string."""
        for pattern, provider in MODEL_TO_PROVIDER.items():
            if pattern.search(model):
                return provider
        return None

    def classify_request(
        self,
        method: str,  # noqa: ARG002
        path: str,
        host: str,
        body: str | None = None,
    ) -> TrafficClassification:
        """Classify a request as AI traffic or not.

        Uses hostname, endpoint path, and optional body inspection.
        """
        hostname_match = self.detect_hostname(host)

        if hostname_match is not None:
            endpoint_type = self._classify_endpoint(path)
            return TrafficClassification(
                is_ai_traffic=True,
                provider=hostname_match.provider,
                endpoint_type=endpoint_type,
                detected_by_hostname=True,
                confidence=hostname_match.confidence,
            )

        is_ai_path = self._is_ai_endpoint(path)
        provider: str | None = None
        confidence = 0.0

        if is_ai_path:
            confidence = 0.6
            if body:
                provider = self._detect_provider_from_body(body)
            return TrafficClassification(
                is_ai_traffic=True,
                provider=provider,
                endpoint_type=self._classify_endpoint(path),
                detected_by_hostname=False,
                confidence=confidence if provider else 0.5,
            )

        if body:
            provider = self._detect_provider_from_body(body)
            if provider is not None:
                return TrafficClassification(
                    is_ai_traffic=True,
                    provider=provider,
                    endpoint_type=None,
                    detected_by_hostname=False,
                    confidence=0.7,
                )

        return TrafficClassification(
            is_ai_traffic=False,
            provider=None,
            detected_by_hostname=False,
            confidence=0.0,
        )

    def _is_ai_endpoint(self, path: str) -> bool:
        return any(pattern.search(path) for pattern in AI_ENDPOINT_PATTERNS)

    def _classify_endpoint(self, path: str) -> str | None:
        path_lower = path.lower()
        if "chat/completions" in path_lower or "/v1/chat" in path_lower:
            return "chat_completion"
        if "completions" in path_lower:
            return "completion"
        if "embeddings" in path_lower:
            return "embedding"
        if "messages" in path_lower:
            return "messages"
        if "models" in path_lower:
            return "models"
        if "generate" in path_lower:
            return "generate"
        return None

    def _detect_provider_from_body(self, body: str) -> str | None:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None

        model = payload.get("model") if isinstance(payload, dict) else None
        if model and isinstance(model, str):
            provider = self.match_model_to_provider(model)
            if provider is not None:
                return provider

        if isinstance(payload, dict) and "messages" in payload:
            msgs = payload["messages"]
            if isinstance(msgs, list) and any(
                isinstance(m, dict) and "role" in m for m in msgs
            ):
                return "openai"

        return None


# ---------------------------------------------------------------------------
# MCPInspector
# ---------------------------------------------------------------------------


class MCPInspector:
    """Parse and inspect MCP (Model Context Protocol) JSON-RPC messages."""

    def parse(self, raw: str) -> MCPMessage | None:
        """Parse a raw string as an MCP JSON-RPC message.

        Returns an ``MCPMessage`` on success, ``None`` on parse failure or
        invalid structure.
        """
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        jsonrpc = data.get("jsonrpc")
        if jsonrpc != "2.0":
            return None

        return MCPMessage(
            jsonrpc=jsonrpc,
            method=data.get("method"),
            params=data.get("params"),
            msg_id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
        )

    def is_mcp(self, raw: str) -> bool:
        """Check whether a raw string is an MCP JSON-RPC message."""
        return self.parse(raw) is not None

    def contains_tool_calls(self, body: str) -> bool:
        """Check if a request body contains tool/function calls."""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return False

        if not isinstance(data, dict):
            return False

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return False

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if "tool_calls" in msg and isinstance(msg["tool_calls"], list) and len(msg["tool_calls"]) > 0:  # noqa
                return True
            if msg.get("role") == "tool":
                return True

        return False

    def extract_tool_names(self, body: str) -> list[str]:
        """Extract tool/function names from a request body."""
        names: list[str] = []
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return names

        if not isinstance(data, dict):
            return names

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return names

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        func = tc.get("function", {})
                        if isinstance(func, dict):
                            name = func.get("name")
                            if isinstance(name, str) and name:
                                names.append(name)

        return names
