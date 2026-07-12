"""Shared Hypothesis strategies and enums for property-based tests.

Provides:
- ``FailureMode`` enum — all 5 failure modes for fail-secure testing (D-162)
- ``PipelinePath`` enum — streaming vs non-streaming pipeline paths
- PII generator strategies: email, phone, credit card, IBAN, name, IP, URL
- ``pii_text_strategy`` — composite strategy embedding synthetic PII into text
- ``all_entity_types`` — list of all supported entity types
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from hypothesis import strategies as st


class FailureMode(Enum):
    """All 5 failure modes that must produce fail-secure behavior (D-162)."""

    DETECTION = "detection_error"
    CACHE = "cache_error"
    FORWARDING_GUARD = "forwarding_denied"
    PROVIDER_TIMEOUT = "provider_timeout"
    CIRCUIT_BREAKER = "circuit_breaker_open"


class PipelinePath(Enum):
    """Pipeline execution paths that must both fail secure (D-164)."""

    NON_STREAMING = "non_streaming"
    STREAMING = "streaming"


# ── PII generation strategies ───────────────────────────────────────────────

email_strategy: st.SearchStrategy[str] = st.emails()

phone_strategy: st.SearchStrategy[str] = st.from_regex(
    r"\+?1?\d{7,15}", fullmatch=True,
)

credit_card_strategy: st.SearchStrategy[str] = st.from_regex(
    r"\d{4}-\d{4}-\d{4}-\d{4}", fullmatch=True,
)

iban_strategy: st.SearchStrategy[str] = st.from_regex(
    r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", fullmatch=True,
)

name_strategy: st.SearchStrategy[str] = st.text(
    min_size=3, max_size=30,
    alphabet=st.characters(min_codepoint=65, max_codepoint=122),
)

ip_strategy: st.SearchStrategy[str] = st.from_regex(
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", fullmatch=True,
)

url_strategy: st.SearchStrategy[str] = st.from_regex(
    r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", fullmatch=True,
)

# ── Composite strategy: sentence with embedded PII ──────────────────────────


@st.composite
def pii_text_strategy(draw: Any) -> tuple[str, str, str]:
    """Generate text containing synthetic PII.

    Returns ``(original_text, entity_value, entity_type)`` so tests can
    verify that ``entity_value`` does not leak into logs while
    ``original_text`` is what the test client sends.
    """
    entity_type = draw(st.sampled_from([
        "EMAIL",
        "PHONE",
        "CREDIT_CARD",
        "IBAN",
        "PERSON",
        "IP",
        "URL",
    ]))
    prefixes: dict[str, st.SearchStrategy[str]] = {
        "EMAIL": email_strategy,
        "PHONE": phone_strategy,
        "CREDIT_CARD": credit_card_strategy,
        "IBAN": iban_strategy,
        "PERSON": name_strategy,
        "IP": ip_strategy,
        "URL": url_strategy,
    }
    entity_value = draw(prefixes[entity_type])
    prefix = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))  # noqa: E501
    suffix = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))  # noqa: E501
    original_text = f"{prefix} {entity_value} {suffix}"
    return original_text.strip(), entity_value, entity_type


# ── Direct strategies per entity type ───────────────────────────────────────

ENTITY_TYPE_STRATEGIES: dict[str, st.SearchStrategy[str]] = {
    "EMAIL": email_strategy,
    "PHONE": phone_strategy,
    "CREDIT_CARD": credit_card_strategy,
    "IBAN": iban_strategy,
    "PERSON": name_strategy,
    "IP": ip_strategy,
    "URL": url_strategy,
}

ALL_ENTITY_TYPES: list[str] = list(ENTITY_TYPE_STRATEGIES)


# ── Failure mode strategies ─────────────────────────────────────────────────

failure_mode_strategy: st.SearchStrategy[FailureMode] = st.sampled_from(list(FailureMode))

pipeline_path_strategy: st.SearchStrategy[PipelinePath] = st.sampled_from(list(PipelinePath))
