"""Luhn, CPF, and CNPJ checksum validators."""

from __future__ import annotations

from anonreq.locale.checksum import ChecksumValidator, digits_only


class LuhnValidator(ChecksumValidator):
    """Standard Luhn mod-10 validator."""

    def validate(self, value: str) -> bool:
        digits = [int(d) for d in digits_only(value)]
        if len(digits) < 2:
            return False
        checksum = 0
        double = False
        for digit in reversed(digits):
            if double:
                digit *= 2
                checksum += digit // 10 + digit % 10
            else:
                checksum += digit
            double = not double
        return checksum % 10 == 0


class CPFValidator(ChecksumValidator):
    """Brazilian CPF validator with two modulo-11 check digits."""

    def validate(self, value: str) -> bool:
        digits = [int(d) for d in digits_only(value)]
        if len(digits) != 11 or len(set(digits)) == 1:
            return False
        first = self._check_digit(digits[:9], range(10, 1, -1))
        second = self._check_digit(digits[:10], range(11, 1, -1))
        return digits[9] == first and digits[10] == second

    @staticmethod
    def _check_digit(digits: list[int], weights: range) -> int:
        total = sum(digit * weight for digit, weight in zip(digits, weights, strict=False))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder


class CNPJValidator(ChecksumValidator):
    """Brazilian CNPJ validator with two modulo-11 check digits."""

    def validate(self, value: str) -> bool:
        digits = [int(d) for d in digits_only(value)]
        if len(digits) != 14 or len(set(digits)) == 1:
            return False
        first = self._check_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        second = self._check_digit(digits[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        return digits[12] == first and digits[13] == second

    @staticmethod
    def _check_digit(digits: list[int], weights: list[int]) -> int:
        total = sum(digit * weight for digit, weight in zip(digits, weights, strict=False))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
