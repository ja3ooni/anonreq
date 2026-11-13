"""BG IBAN shapes: strict for the verified type, loose for the unverified one.

IBAN_BG (verified): BGkk + 4 letters + 6 digits + 8 alphanumerics, MOD-97.
IBAN_BG_UNVERIFIED: BGkk + 4 letters + 14 alphanumerics, any case, any
checksum, so a mistyped branch/account-type digit still fails closed.
"""

from __future__ import annotations

import pytest

from anonreq.detection.regex_detector import RegexDetector
from anonreq.locale.checksums.bulgaria import generate_iban_bg, iban_bg_valid
from anonreq.locale.registry import LocaleRegistry


def _mod97_iban(bank: str, bban14: str) -> str:
    """Any-shape BG IBAN with correct check digits (bypasses the strict generator)."""
    rearranged = f"{bank}{bban14}BG00"
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    check = 98 - int(digits) % 97
    return f"BG{check:02d}{bank}{bban14}"


@pytest.fixture(scope="module")
def patterns():
    bundle = LocaleRegistry("config/locales").get("bg-BG")
    assert bundle is not None
    return RegexDetector.patterns_from_entity_configs(bundle.entity_types)


def _types(patterns, text: str, value: str) -> set[str]:
    start = text.index(value)
    return {
        d["entity_type"]
        for d in RegexDetector().detect(text, extra_patterns=patterns)
        if d["start"] <= start and d["end"] >= start + len(value)
    }


def test_strict_iban_is_verified(patterns) -> None:
    iban = generate_iban_bg("SYNT", "12345678901234")
    assert "IBAN_BG" in _types(patterns, f"IBAN {iban} please", iban)


@pytest.mark.parametrize(
    "bban14",
    [
        "1A3456789012AB",  # letter in the 6-digit branch/account-type part
        "ABCDEF78901234",  # letters only where digits belong
    ],
)
def test_loose_shape_with_valid_checksum_is_unverified_not_dropped(patterns, bban14: str) -> None:
    iban = _mod97_iban("SYNT", bban14)
    assert not iban_bg_valid(iban)  # strict shape check fails
    types = _types(patterns, f"IBAN {iban} please", iban)
    assert "IBAN_BG" not in types
    assert "IBAN_BG_UNVERIFIED" in types


@pytest.mark.parametrize(
    "value",
    [
        "BG80SYNT1A3456789012AB",  # loose shape, bad checksum
        "bg80synt123456789012ab",  # lower case
        "BG80 SYNT 1A34 5678 9012 AB",  # spaced, loose shape
    ],
)
def test_mistyped_ibans_fail_closed(patterns, value: str) -> None:
    assert "IBAN_BG_UNVERIFIED" in _types(patterns, f"плащане по {value}.", value)


@pytest.mark.parametrize(
    "value",
    [
        "BG80SYNT1234567890123",  # 13 alphanumerics: too short
        "BG80SY1T12345678901234",  # digit in the bank code
        "ORDER-BG80SYNT12345678901234",  # glued to a word
    ],
)
def test_non_iban_shapes_do_not_match(patterns, value: str) -> None:
    types = _types(patterns, f"ref {value} ok", value)
    assert not types & {"IBAN_BG", "IBAN_BG_UNVERIFIED"}
