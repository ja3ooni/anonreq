"""Proxy-only mode — minimal-overhead passthrough with no anonymization.

Provides:
- ``ProxyOnlyHandler`` — forwards requests without sanitization
- ``GatewayStatus`` — runtime gateway metadata and configuration
- ``ProxyMode`` — mode enumeration
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class ProxyMode(enum.StrEnum):
    PROXY_ONLY = "proxy-only"
    FULL = "full"
    TRANSPARENT = "transparent"


# Default set of known/allowed AI providers
DEFAULT_ALLOWED_PROVIDERS: list[str] = [
    "openai",
    "anthropic",
    "gemini",
    "ollama",
    "deepseek",
    "mistral",
    "cohere",
    "together",
    "perplexity",
]


@dataclass
class _GatewayState:
    mode: ProxyMode = ProxyMode.PROXY_ONLY
    block_all_unintercepted_ai: bool = False
    allowed_providers: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_PROVIDERS))
    start_time: float = field(default_factory=time.monotonic)


class ProxyOnlyHandler:
    """Handle proxy-only requests with minimal overhead.

    Proxy-only mode forwards requests without anonymization or detection.
    Latency target: P95 ≤ 5ms for the handler itself (excluding network I/O).

    Args:
        block_all_unintercepted_ai: If true, AI traffic not going through
            the gateway is blocked.
    """

    def __init__(self, block_all_unintercepted_ai: bool = False) -> None:
        self._state = _GatewayState()
        self._state.mode = ProxyMode.PROXY_ONLY
        self._state.block_all_unintercepted_ai = block_all_unintercepted_ai

    @property
    def mode(self) -> ProxyMode:
        return self._state.mode

    @property
    def block_all_unintercepted_ai(self) -> bool:
        return self._state.block_all_unintercepted_ai

    async def passthrough(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> dict[str, Any]:
        """Forward a request without sanitization.

        Returns a response dict indicating the request was forwarded
        without anonymization. In production, this would perform the
        actual upstream HTTP call.

        Latency for this method (excluding I/O) must remain under 1ms
        to meet P95 ≤ 5ms end-to-end budget.
        """
        return {
            "status": "forwarded",
            "mode": self._state.mode.value,
            "anonymization_applied": False,
            "method": method,
            "path": path,
            "headers": headers,
            "body": body,
        }


class GatewayStatus:
    """Runtime gateway status and configuration.

    Provides the data backing for ``GET /v1/gateway/status``.
    """

    def __init__(self) -> None:
        self._state = _GatewayState()

    def get_status(self) -> dict[str, Any]:
        """Return current gateway status information."""
        uptime = time.monotonic() - self._state.start_time
        return {
            "service": "AnonReq Gateway",
            "mode": self._state.mode.value,
            "uptime_seconds": round(uptime, 1),
            "proxy_config": {
                "block_all_unintercepted_ai": self._state.block_all_unintercepted_ai,
                "allowed_providers": list(self._state.allowed_providers),
            },
        }

    def set_mode(self, mode: str) -> None:
        """Set the gateway operating mode."""
        self._state.mode = ProxyMode(mode)
