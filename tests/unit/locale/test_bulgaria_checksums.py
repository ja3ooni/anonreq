"""Bulgarian checksum validators. Synthetic, generator-built values only."""

from __future__ import annotations

import datetime as dt

import pytest

from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.checksums.bulgaria import (
    egn_birth_date,
    egn_check_digit,
    egn_valid,
    eik_valid,
    generate_egn,
    generate_eik,
    generate_iban_bg,
    generate_lnch,
    iban_bg_valid,
    lnch_valid,
)
from anonreq.locale.registry import LocaleRegistry


def _flip_last(value: str) -> str:
    return value[:-1] + str((int(value[-1]) + 1) % 10)


@pytest.mark.parametrize(
    ("birth", "month_digits"),
    [
        (dt.date(1985, 3, 15), "03"),  # 1900s: month as is
        (dt.date(1899, 12, 31), "32"),  # 1800s: +20
        (dt.date(2004, 7, 1), "47"),  # 2000s: +40
        (dt.date(2000, 2, 29), "42"),  # leap day
    ],
)
def test_egn_generated_values_validate_and_decode(birth: dt.date, month_digits: str) -> None:
    egn = generate_egn(birth, serial=456)
    assert len(egn) == 10
    assert egn.isdigit()
    assert egn[2:4] == month_digits
    assert egn_valid(egn)
    assert egn_birth_date(egn) == birth
    assert not egn_valid(_flip_last(egn))


def test_egn_weights_and_remainder_ten() -> None:
    # 2,4,8,5,10,9,7,3,6 mod 11; a remainder of 10 gives check digit 0.
    body = "850315456"
    total = sum(int(d) * w for d, w in zip(body, (2, 4, 8, 5, 10, 9, 7, 3, 6), strict=True))
    assert egn_check_digit(body) == str(total % 11 % 10)
    ten = next(
        f"8503{day:02d}{serial:03d}"
        for day in range(1, 29)
        for serial in range(1000)
        if sum(int(d) * w for d, w in zip(f"8503{day:02d}{serial:03d}",
                                          (2, 4, 8, 5, 10, 9, 7, 3, 6), strict=True)) % 11 == 10
    )
    assert egn_check_digit(ten) == "0"
    assert egn_valid(ten + "0")


@pytest.mark.parametrize(
    "value", ["8513154560", "8502304561", "0000000000", "85031545", "85031545612"]
)
def test_egn_rejects_impossible_dates_and_lengths(value: str) -> None:
    # month 13, 30 February, all zeros, too short, too long
    assert not egn_valid(value)


def test_lnch_generated_value_validates() -> None:
    lnch = generate_lnch("100200300")
    weights = (21, 19, 17, 13, 11, 9, 7, 3, 1)
    total = sum(int(d) * w for d, w in zip("100200300", weights, strict=True))
    assert lnch[-1] == str(total % 10)
    assert lnch_valid(lnch)
    assert not lnch_valid(_flip_last(lnch))
    assert not lnch_valid("10020030")


def test_eik_nine_and_thirteen_digits() -> None:
    eik9 = generate_eik("20406080")
    eik13 = generate_eik("20406080", "001")
    assert len(eik9) == 9
    assert len(eik13) == 13
    assert eik13.startswith(eik9)
    assert eik_valid(eik9)
    assert eik_valid(eik13)
    assert eik_valid("BG" + eik9)  # VAT number form
    assert not eik_valid(_flip_last(eik9))
    assert not eik_valid(_flip_last(eik13))
    assert not eik_valid(_flip_last(eik9) + eik13[9:])  # bad 9-digit stage
    assert not eik_valid("000000000")
    assert not eik_valid("1234567890")  # 10 digits is not an EIK length


def test_eik_fallback_weights() -> None:
    # Find a body whose 1..8 weighted sum is 10 mod 11: the check digit then
    # comes from weights 3..10 (and is 0 if that is 10 as well).
    body = next(
        f"{n:08d}" for n in range(10_000_000, 10_100_000)
        if sum(int(d) * w for d, w in zip(f"{n:08d}", range(1, 9), strict=True)) % 11 == 10
    )
    second = sum(int(d) * w for d, w in zip(body, range(3, 11), strict=True)) % 11
    expected = "0" if second == 10 else str(second)
    assert generate_eik(body)[-1] == expected
    assert eik_valid(generate_eik(body))


def test_iban_bg_layout_and_mod97() -> None:
    iban = generate_iban_bg("SYNT", "12345678901234")
    assert len(iban) == 22
    assert iban.startswith("BG")
    assert iban_bg_valid(iban)
    assert iban_bg_valid(" ".join(iban[i:i + 4] for i in range(0, 22, 4)))
    assert iban_bg_valid(iban.lower())  # validator is case-blind; the pattern is not
    broken = iban[:-1] + str((int(iban[-1]) + 1) % 10)
    assert not iban_bg_valid(broken)
    assert not iban_bg_valid(iban[:-1])  # 21 characters
    assert not iban_bg_valid("BG" + iban[2:4] + "12" + iban[6:])  # bank code must be letters


def test_registry_registers_bulgarian_validators() -> None:
    checksums = ChecksumValidatorRegistry()
    registry = LocaleRegistry("config/locales", checksum_registry=checksums)
    bundle = registry.get("bg-BG")
    assert bundle is not None
    assert {"EGN", "LNCH", "EIK", "IBAN_BG"} <= checksums.registered_entity_types()
    assert checksums.validate("EGN", generate_egn(dt.date(1990, 1, 2)))
    assert not checksums.validate("LNCH", _flip_last(generate_lnch()))
