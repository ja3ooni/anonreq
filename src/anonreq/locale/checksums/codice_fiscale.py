"""Italian Codice Fiscale checksum validator."""

from __future__ import annotations

import string

from anonreq.locale.checksum import ChecksumValidator

_ODD_VALUES = {
    **{str(i): v for i, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
    **dict(zip(string.ascii_uppercase, [
        1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18,
        20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23,
    ])),
}


class CodiceFiscaleValidator(ChecksumValidator):
    """Validate the final check character of an Italian Codice Fiscale."""

    def validate(self, value: str) -> bool:
        code = "".join(ch for ch in value.upper() if ch.isalnum())
        if len(code) != 16:
            return False
        total = 0
        for idx, char in enumerate(code[:15], start=1):
            if idx % 2 == 1:
                total += _ODD_VALUES.get(char, -1000)
            elif char.isdigit():
                total += int(char)
            else:
                total += ord(char) - ord("A")
        expected = chr(ord("A") + (total % 26))
        return expected == code[-1]
