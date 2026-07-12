"""Proxy mode definitions and mode-dependent pipeline routing.

Provides:
- ``ProxyMode`` enum with three modes: proxy-only, full, transparent
- ``get_pipeline_for_mode()`` — returns ordered pipeline stage names for a mode
- ``requires_mitm()`` — whether a mode needs MITM TLS interception
- ``requires_detection()`` — whether a mode needs PII detection/anonymization
- ``mode_from_env()`` — reads and validates ``ANONREQ_PROXY_MODE`` env var
- ``proxy_mode_description()`` — human-readable mode descriptions

Per D-014, D-015, D-016, D-020, D-021:
- Proxy-only: routing + TLS + audit only, P50 < 2ms, P95 < 5ms, P99 < 10ms
- Full: all pipeline stages including detection and anonymization
- Transparent: same as Full but with MITM TLS interception
- Mode is read from env var at startup and is immutable at runtime
"""

from __future__ import annotations

import enum
import os
from typing import Final

from anonreq.exceptions import AnonReqError

# ---------------------------------------------------------------------------
# Pipeline stage definitions per mode
# ---------------------------------------------------------------------------

PROXY_ONLY_STAGES: Final[list[str]] = [
    "auth",
    "routing",
    "forwarding_guard",
    "audit",
]
"""Pipeline stages for proxy-only mode — minimal overhead, no detection."""

FULL_STAGES: Final[list[str]] = [
    "auth",
    "routing",
    "classification",
    "detection",
    "anonymization",
    "forwarding_guard",
    "provider_call",
    "restoration",
    "audit",
]
"""Pipeline stages for full inspection mode — all capabilities enabled."""


class ProxyMode(enum.StrEnum):
    """Gateway operating modes.

    Each mode defines which pipeline stages are active and how the
    gateway processes incoming requests.

    Attributes:
        PROXY_ONLY: Minimal-overhead routing + TLS + audit. Skips all
            detection, anonymization, and classification. Target latency:
            P50 < 2ms / P95 < 5ms / P99 < 10ms.
        FULL: Full inspection pipeline including detection, anonymization,
            classification, and restoration. Standard latency budget.
        TRANSPARENT: Same pipeline as FULL, but also enables MITM TLS
            interception for transparent proxy deployments.
    """

    PROXY_ONLY = "proxy-only"
    FULL = "full"
    TRANSPARENT = "transparent"


def get_pipeline_for_mode(mode: ProxyMode) -> list[str]:
    """Return the ordered list of pipeline stage names for the given mode.

    Args:
        mode: The operating mode.

    Returns:
        A list of stage name strings in execution order.
    """
    if mode == ProxyMode.PROXY_ONLY:
        return list(PROXY_ONLY_STAGES)
    # FULL and TRANSPARENT share the same pipeline
    return list(FULL_STAGES)


def requires_mitm(mode: ProxyMode) -> bool:
    """Return whether the mode needs MITM TLS interception.

    Only transparent proxy mode requires MITM. Proxy-only and full
    modes operate as a forward/reverse proxy without TLS interception.

    Args:
        mode: The operating mode.

    Returns:
        ``True`` if the mode needs MITM TLS interception.
    """
    return mode == ProxyMode.TRANSPARENT


def requires_detection(mode: ProxyMode) -> bool:
    """Return whether the mode needs PII detection and anonymization.

    Only proxy-only mode skips detection. Full and transparent modes
    include the full detection/anonymization pipeline.

    Args:
        mode: The operating mode.

    Returns:
        ``True`` if the mode needs PII detection.
    """
    return mode != ProxyMode.PROXY_ONLY


def mode_from_env() -> ProxyMode:
    """Read and validate the ``ANONREQ_PROXY_MODE`` environment variable.

    Reads the env var, validates against known ``ProxyMode`` values, and
    returns the corresponding enum member. Falls back to ``FULL`` if the
    env var is not set.

    Returns:
        The validated ``ProxyMode`` enum member.

    Raises:
        ConfigurationError: If the env var value is not a valid proxy mode.
    """
    raw = os.environ.get("ANONREQ_PROXY_MODE", "full").strip().lower()

    for mode in ProxyMode:
        if mode.value == raw:
            return mode

    valid = ", ".join(m.value for m in ProxyMode)
    raise AnonReqError(
        message=f"Invalid proxy mode '{raw}'. Valid modes: {valid}",
        error_type="configuration_error",
        status_code=500,
        code="invalid_proxy_mode",
    )


def proxy_mode_description(mode: ProxyMode) -> str:
    """Return a human-readable description of the given mode.

    Args:
        mode: The operating mode.

    Returns:
        A descriptive string explaining what the mode does.
    """
    descriptions = {
        ProxyMode.PROXY_ONLY: (
            "Proxy-only mode: routes traffic with TLS termination and audit "
            "logging only. No PII detection, no anonymization, no content "
            "classification. Latency target: P50 < 2ms / P95 < 5ms / P99 < 10ms."
        ),
        ProxyMode.FULL: (
            "Full inspection mode: all pipeline stages active including PII "
            "detection, anonymization, content classification, and response "
            "restoration. Standard latency budget."
        ),
        ProxyMode.TRANSPARENT: (
            "Transparent proxy mode: same as full inspection with additional "
            "MITM TLS interception. Requires tenant CA certificate for TLS "
            "termination and re-origination."
        ),
    }
    return descriptions.get(mode, "Unknown mode")
