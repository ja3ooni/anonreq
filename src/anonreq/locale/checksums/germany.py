"""German national-identifier checksum validators.

Covers the identifiers a German CISO/DPO expects in a PDPL-equivalent pack:
Steuer-ID, Personalausweis, KVNR, and DE IBAN (ISO 13616 MOD-97).
"""

from __future__ import annotations

import re

from anonreq.locale.checksum import ChecksumValidator, digits_only

_ICAO_VALUES: dict[str, int] = {
    **{str(i): i for i in range(10)},
    **{chr(ord("A") + i): 10 + i for i in range(26)},
}
_ICAO_WEIGHTS = (7, 3, 1)

_IBAN_RE = re.compile(r"^DE\d{20}$")
_KVNR_RE = re.compile(r"^[A-Z]\d{9}$")
_AUSWEIS_RE = re.compile(r"^[A-Z](?!\d{9}$)[A-Z0-9]{8}\d$")


def iso7064_mod11_10_check_digit(body10: str) -> str:
    """Return the 11th Steuer-ID digit for a 10-digit body."""
    product = 10
    for char in body10:
        total = (int(char) + product) % 10
        if total == 0:
            total = 10
        product = (2 * total) % 11
    check = 11 - product
    if check in (10, 11):
        check = 0
    return str(check)


def generate_steuer_id(body10: str = "1234567890") -> str:
    """Build a checksum-valid 11-digit Steuer-ID."""
    digits = digits_only(body10)
    if len(digits) != 10 or digits[0] == "0":
        raise ValueError("Steuer-ID body must be 10 digits and must not start with 0")
    return digits + iso7064_mod11_10_check_digit(digits)


def icao9303_check_digit(body: str) -> str:
    """ICAO 9303 / MRZ check digit (weights 7-3-1, A=10…Z=35)."""
    total = 0
    for idx, char in enumerate(body.upper()):
        total += _ICAO_VALUES.get(char, 0) * _ICAO_WEIGHTS[idx % 3]
    return str(total % 10)


def generate_personalausweis(body9: str = "L01X00T47") -> str:
    """Build a 10-character Personalausweis number (9-char body + check digit)."""
    compact = "".join(ch for ch in body9.upper() if ch.isalnum())
    if len(compact) != 9:
        raise ValueError("Personalausweis body must be 9 alphanumeric characters")
    return compact + icao9303_check_digit(compact)


def kvnr_check_digit(letter: str, serial8: str) -> str:
    """Luhn check digit over letter→2-digit mapping plus 8 serial digits."""
    letter_num = f"{ord(letter.upper()) - ord('A') + 1:02d}"
    payload = letter_num + serial8
    digits = [int(d) for d in payload]
    checksum = 0
    double = True
    for digit in reversed(digits):
        if double:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
        double = not double
    return str((10 - (checksum % 10)) % 10)


def generate_kvnr(letter: str = "A", serial8: str = "12345678") -> str:
    """Build a checksum-valid KVNR (letter + 8 digits + check)."""
    if len(letter) != 1 or not letter.isalpha() or len(serial8) != 8 or not serial8.isdigit():
        raise ValueError("KVNR requires one letter and an 8-digit serial")
    return f"{letter.upper()}{serial8}{kvnr_check_digit(letter, serial8)}"


def generate_iban_de(blz: str = "37040044", account: str = "0532013000") -> str:
    """Build a MOD-97-valid German IBAN from BLZ + account number."""
    bban = f"{digits_only(blz):0>8}{digits_only(account):0>10}"[:18]
    numeric = bban + "131400"  # D=13, E=14, check placeholder 00
    check = 98 - (int(numeric) % 97)
    return f"DE{check:02d}{bban}"


def iban_mod97_valid(value: str) -> bool:
    compact = value.replace(" ", "").upper()
    if len(compact) < 15 or not compact[:2].isalpha() or not compact[2:4].isdigit():
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(
        str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged
    )
    if not numeric.isdigit():
        return False
    return int(numeric) % 97 == 1


class PersonalausweisValidator(ChecksumValidator):
    """Validate a German Personalausweis number with ICAO 9303 check digit."""

    def validate(self, value: str) -> bool:
        compact = "".join(ch for ch in value.upper() if ch.isalnum())
        if not _AUSWEIS_RE.match(compact):
            return False
        return compact[-1] == icao9303_check_digit(compact[:9])


class KVNRValidator(ChecksumValidator):
    """Validate a German Krankenversichertennummer (letter + 9 digits)."""

    def validate(self, value: str) -> bool:
        compact = value.replace(" ", "").upper()
        if not _KVNR_RE.match(compact):
            return False
        expected = kvnr_check_digit(compact[0], compact[1:9])
        return compact[9] == expected


class IBANMod97Validator(ChecksumValidator):
    """ISO 13616 IBAN check (MOD-97). Restricts to DE when the value is German."""

    def validate(self, value: str) -> bool:
        compact = value.replace(" ", "").upper()
        if compact.startswith("DE") and not _IBAN_RE.match(compact):
            return False
        return iban_mod97_valid(compact)
