"""Bulgarian national-identifier checksum validators.

Covers the identifiers a Bulgarian DPO expects the gateway to mask:

* EGN (ЕГН): 10 digits, YYMMDD birth date with the month offset by +20
  for 1800s births and +40 for 2000s births, then a weighted mod-11 check
  digit (weights 2,4,8,5,10,9,7,3,6; a remainder of 10 counts as 0).
* LNCh (ЛНЧ): 10 digits, weights 21,19,17,13,11,9,7,3,1, sum mod 10.
* EIK / BULSTAT (ЕИК / БУЛСТАТ): 9 digits (weights 1..8, falling back to
  3..10, mod 11) or 13 digits (the 9-digit check plus a second stage over
  digits 9-12 with weights 2,7,3,5, falling back to 4,9,5,7).
* BG IBAN: ``BGkk`` + 4-letter bank code + 6 digits (branch and account
  type) + 8 alphanumerics, ISO 13616
  MOD-97.

The Bulgarian ID card number (лична карта) has no public checksum, so it
has no validator here; the locale bundle matches it on context only.

The ``generate_*`` helpers build checksum-valid synthetic values for tests.
"""

from __future__ import annotations

import datetime as _dt
import re

from anonreq.locale.checksum import ChecksumValidator
from anonreq.locale.checksums.germany import iban_mod97_valid

_EGN_WEIGHTS = (2, 4, 8, 5, 10, 9, 7, 3, 6)
_LNCH_WEIGHTS = (21, 19, 17, 13, 11, 9, 7, 3, 1)
_EIK9_WEIGHTS = (1, 2, 3, 4, 5, 6, 7, 8)
_EIK9_FALLBACK = (3, 4, 5, 6, 7, 8, 9, 10)
_EIK13_WEIGHTS = (2, 7, 3, 5)
_EIK13_FALLBACK = (4, 9, 5, 7)

_IBAN_BG_RE = re.compile(r"^BG\d{2}[A-Z]{4}\d{6}[A-Z0-9]{8}$")
_SEPARATORS = re.compile(r"[\s./-]")


def _compact(value: str) -> str:
    return _SEPARATORS.sub("", value.strip()).upper()


# --------------------------------------------------------------------------
# EGN
# --------------------------------------------------------------------------


def egn_check_digit(body9: str) -> str:
    """Return the EGN check digit for the first nine digits."""
    total = sum(int(d) * w for d, w in zip(body9, _EGN_WEIGHTS, strict=True))
    return str(total % 11 % 10)


def egn_birth_date(egn: str) -> _dt.date | None:
    """Decode the birth date in an EGN, or None when it is not a real date."""
    if len(egn) < 6 or not egn[:6].isdigit():
        return None
    year, month, day = int(egn[0:2]), int(egn[2:4]), int(egn[4:6])
    if month > 40:
        year, month = 2000 + year, month - 40
    elif month > 20:
        year, month = 1800 + year, month - 20
    else:
        year += 1900
    try:
        return _dt.date(year, month, day)
    except ValueError:
        return None


def egn_valid(value: str) -> bool:
    compact = _compact(value)
    if len(compact) != 10 or not compact.isdigit():
        return False
    if egn_birth_date(compact) is None:
        return False
    return compact[9] == egn_check_digit(compact[:9])


def generate_egn(birth: _dt.date, serial: int = 123) -> str:
    """Build a checksum-valid EGN for ``birth`` and a 3-digit serial."""
    if not 1800 <= birth.year <= 2099:
        raise ValueError("EGN covers births from 1800 to 2099")
    month = birth.month
    if birth.year >= 2000:
        month += 40
    elif birth.year < 1900:
        month += 20
    body = f"{birth.year % 100:02d}{month:02d}{birth.day:02d}{serial % 1000:03d}"
    return body + egn_check_digit(body)


# --------------------------------------------------------------------------
# LNCh
# --------------------------------------------------------------------------


def lnch_check_digit(body9: str) -> str:
    total = sum(int(d) * w for d, w in zip(body9, _LNCH_WEIGHTS, strict=True))
    return str(total % 10)


def lnch_valid(value: str) -> bool:
    compact = _compact(value)
    if len(compact) != 10 or not compact.isdigit():
        return False
    return compact[9] == lnch_check_digit(compact[:9])


def generate_lnch(body9: str = "100200300") -> str:
    if len(body9) != 9 or not body9.isdigit():
        raise ValueError("LNCh body must be 9 digits")
    return body9 + lnch_check_digit(body9)


# --------------------------------------------------------------------------
# EIK / BULSTAT
# --------------------------------------------------------------------------


def _mod11_with_fallback(digits: str, weights: tuple[int, ...], fallback: tuple[int, ...]) -> str:
    remainder = sum(int(d) * w for d, w in zip(digits, weights, strict=True)) % 11
    if remainder == 10:
        remainder = sum(int(d) * w for d, w in zip(digits, fallback, strict=True)) % 11
        if remainder == 10:
            remainder = 0
    return str(remainder)


def eik9_check_digit(body8: str) -> str:
    return _mod11_with_fallback(body8, _EIK9_WEIGHTS, _EIK9_FALLBACK)


def eik13_check_digit(body12: str) -> str:
    return _mod11_with_fallback(body12[8:12], _EIK13_WEIGHTS, _EIK13_FALLBACK)


def eik_valid(value: str) -> bool:
    compact = _compact(value)
    if compact.startswith("BG"):  # VAT number form: BG + EIK
        compact = compact[2:]
    if len(compact) not in (9, 13) or not compact.isdigit():
        return False
    if not compact.strip("0"):  # all zeros passes the arithmetic but is no EIK
        return False
    if compact[8] != eik9_check_digit(compact[:8]):
        return False
    if len(compact) == 13:
        return compact[12] == eik13_check_digit(compact[:12])
    return True


def generate_eik(body8: str = "20406080", branch3: str | None = None) -> str:
    """Build a 9-digit EIK, or a 13-digit branch EIK when ``branch3`` is given."""
    if len(body8) != 8 or not body8.isdigit():
        raise ValueError("EIK body must be 8 digits")
    eik9 = body8 + eik9_check_digit(body8)
    if branch3 is None:
        return eik9
    if len(branch3) != 3 or not branch3.isdigit():
        raise ValueError("EIK branch suffix must be 3 digits")
    body12 = eik9 + branch3
    return body12 + eik13_check_digit(body12)


# --------------------------------------------------------------------------
# BG IBAN
# --------------------------------------------------------------------------


def iban_bg_valid(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    if not _IBAN_BG_RE.match(compact):
        return False
    return iban_mod97_valid(compact)


def generate_iban_bg(bank: str = "SYNT", bban14: str = "12345678901234") -> str:
    """Build a MOD-97-valid Bulgarian IBAN (22 characters)."""
    bank = bank.upper()
    bban14 = bban14.upper()
    if (
        len(bank) != 4
        or not bank.isalpha()
        or len(bban14) != 14
        or not bban14[:6].isdigit()
        or not bban14[6:].isalnum()
    ):
        raise ValueError("BG IBAN needs a 4-letter bank code, 6 digits and 8 alphanumerics")
    bban = bank + bban14
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in bban + "BG00")
    check = 98 - (int(numeric) % 97)
    return f"BG{check:02d}{bban}"


# --------------------------------------------------------------------------
# Registry validators
# --------------------------------------------------------------------------


class EGNValidator(ChecksumValidator):
    """Bulgarian EGN: real birth date plus weighted mod-11 check digit."""

    def validate(self, value: str) -> bool:
        return egn_valid(value)


class LNChValidator(ChecksumValidator):
    """Bulgarian LNCh (foreigner personal number): weighted mod-10."""

    def validate(self, value: str) -> bool:
        return lnch_valid(value)


class EIKValidator(ChecksumValidator):
    """Bulgarian EIK / BULSTAT, 9 or 13 digits, optional BG VAT prefix."""

    def validate(self, value: str) -> bool:
        return eik_valid(value)


class IBANBGValidator(ChecksumValidator):
    """Bulgarian IBAN: exact BG layout plus ISO 13616 MOD-97."""

    def validate(self, value: str) -> bool:
        return iban_bg_valid(value)


# Used by RegexDetector to drop checksum-invalid candidates before overlap
# resolution, so an invalid EGN cannot win the span from a valid LNCh or a
# phone number that covers the same digits.
PREFILTER_VALIDATORS = {
    "EGN": egn_valid,
    "LNCH": lnch_valid,
    "EIK": eik_valid,
    "IBAN_BG": iban_bg_valid,
}
