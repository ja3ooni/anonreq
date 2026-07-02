"""French NIR checksum validator."""

from __future__ import annotations

from anonreq.locale.checksum import ChecksumValidator, digits_only


class NIRValidator(ChecksumValidator):
    """Validate French NIR values using the two-digit key."""

    def validate(self, value: str) -> bool:
        digits = digits_only(value)
        if len(digits) != 15:
            return False
        if digits[0] not in {"1", "2"}:
            return False
        month = int(digits[3:5])
        if month < 1 or month > 12:
            return False
        body = int(digits[:13])
        key = int(digits[13:])
        return 97 - (body % 97) == key
