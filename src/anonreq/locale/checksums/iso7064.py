"""ISO 7064 Mod 11,10 style validator for German Steuer-ID."""

from __future__ import annotations

from anonreq.locale.checksum import ChecksumValidator, digits_only


class ISO7064Mod11_2Validator(ChecksumValidator):  # noqa: N801
    """Validate an 11-digit German Steuer-ID checksum."""

    def validate(self, value: str) -> bool:
        digits = digits_only(value)
        if len(digits) != 11 or not digits.isdigit():
            return False

        product = 10
        for char in digits[:10]:
            total = (int(char) + product) % 10
            if total == 0:
                total = 10
            product = (2 * total) % 11

        check = 11 - product
        if check == 10:
            check = 0
        if check == 11:
            check = 0
        return check == int(digits[-1])
