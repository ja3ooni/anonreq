"""Pre-compiled regex patterns for deterministic PII detection.

Per D-36, D-38, D-41:
- Tier 1 entities are always enabled (email, phone, credit card, etc.)
- Tier 2 entities are configurable (SSN, SWIFT, CRYPTO)
- All regex results get score=1.0 (deterministic per D-38)
- Luhn checksum inline function — avoids external dependency
- ENTITY_SPECIFICITY provides single-source-of-truth for span arbitration
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Pre-compiled regex patterns
# ---------------------------------------------------------------------------

PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL_ADDRESS": re.compile(
        r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}"
    ),
    "PHONE_NUMBER": re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:\d[ -]*?){13,19}\b"
    ),
    "IBAN_CODE": re.compile(
        r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,7}[A-Z0-9]{1,4}\b"
    ),
    "IP_ADDRESS": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
    "URL": re.compile(
        r"https?://[^\s/$.?#].[^\s]*"
    ),
    "US_SSN": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
    ),
}

# ---------------------------------------------------------------------------
# Entity tiers (D-36)
# ---------------------------------------------------------------------------

TIER_1_ENTITIES: list[str] = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
]

TIER_2_ENTITIES: list[str] = [
    "US_SSN",
    "SWIFT_CODE",
    "CRYPTO",
]

# ---------------------------------------------------------------------------
# Entity specificity ranking (D-41)
# ---------------------------------------------------------------------------

ENTITY_SPECIFICITY: dict[str, int] = {
    "API_KEY": 100,
    "EMAIL_ADDRESS": 90,
    "PHONE_NUMBER": 80,
    "CREDIT_CARD": 75,
    "IBAN_CODE": 70,
    "US_SSN": 65,
    "URL": 55,
    "IP_ADDRESS": 50,
    "PERSON": 40,
    "DATE_TIME": 35,
    "LOCATION": 30,
    "ORGANIZATION": 25,
}

# ---------------------------------------------------------------------------
# Luhn checksum validation
# ---------------------------------------------------------------------------


def luhn_checksum(card_number: str) -> bool:
    """Validate a credit card number using the Luhn algorithm.

    Strips non-digit characters, checks length (13-19 digits),
    and applies the Luhn mod-10 checksum.

    Args:
        card_number: Raw card number string (may include spaces/dashes).

    Returns:
        ``True`` if the number passes the Luhn check, ``False`` otherwise.
    """
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    # Luhn algorithm: double every second digit from the right
    checksum = 0
    is_second = False
    for d in reversed(digits):
        if is_second:
            doubled = d * 2
            checksum += doubled // 10 + doubled % 10
        else:
            checksum += d
        is_second = not is_second

    return checksum % 10 == 0
