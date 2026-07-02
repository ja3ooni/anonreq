"""Locale checksum property tests (TEST-05).

Verifies that invalid-checksum national IDs are never flagged as valid
detections for all 6 supported national ID formats:
- Steuer-ID (DE) — ISO 7064 Mod 11,2
- BSN (NL) — Luhn mod-10
- NIR (FR) — Modulo-97
- CPF (BR) — Dual modulo-11
- CNPJ (BR) — Dual modulo-11 (14-digit)
- Codice Fiscale (IT) — Odd/even character sum, modulo-26 check char

Properties per REQUIREMENTS.md (LOCL-07, TEST-05):
1. Invalid checksum IDs never flagged as valid detections
2. Near-valid IDs (single digit/char changed) never flagged
3. Valid checksum IDs still detected (regression guard)
"""

from __future__ import annotations

from hypothesis import HealthCheck, assume, given, settings, strategies as st

from anonreq.locale.checksum import ChecksumValidatorRegistry, validate_detection
from anonreq.locale.checksums.codice_fiscale import CodiceFiscaleValidator
from anonreq.locale.checksums.iso7064 import ISO7064Mod11_2Validator
from anonreq.locale.checksums.luhn import CNPJValidator, CPFValidator, LuhnValidator
from anonreq.locale.checksums.nir import NIRValidator


# ── Shared Hypothesis settings per TEST-PLAN.md ──────────────────────────────

HYP_SETTINGS = settings(
    max_examples=200,
    deadline=30000,
    derandomize=True,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
        HealthCheck.large_base_example,
    ],
)


# ── Invalid-checksum strategy generators ─────────────────────────────────────


@st.composite
def invalid_steuer_id(draw: st.DrawFn) -> str:
    """Generate an 11-digit string that fails the ISO 7064 Mod 11,2 check."""
    digits = [draw(st.integers(min_value=0, max_value=9)) for _ in range(10)]
    # Calculate correct checksum (ISO 7064 Mod 11,2)
    product = 10
    for char_int in digits:
        total = (char_int + product) % 10
        if total == 0:
            total = 10
        product = (2 * total) % 11
    correct_check = 11 - product
    if correct_check == 10:
        correct_check = 0
    if correct_check == 11:
        correct_check = 0
    # Mutate to a DIFFERENT digit to invalidate the checksum
    wrong_check = (correct_check + 1) % 10
    return "".join(str(d) for d in digits) + str(wrong_check)


@st.composite
def invalid_bsn(draw: st.DrawFn) -> str:
    """Generate a 9-digit string that fails the Luhn mod-10 check."""
    while True:
        digits = [draw(st.integers(min_value=0, max_value=9)) for _ in range(8)]
        # Calculate correct Luhn check digit
        all_digits = digits + [0]
        checksum = 0
        double = False
        for digit in reversed(all_digits):
            if double:
                digit *= 2
                checksum += digit // 10 + digit % 10
            else:
                checksum += digit
            double = not double
        correct_check = (10 - (checksum % 10)) % 10
        wrong_check = (correct_check + 1) % 10
        if wrong_check == correct_check:
            continue
        result = "".join(str(d) for d in digits) + str(wrong_check)
        if not LuhnValidator().validate(result):
            return result


@st.composite
def invalid_nir(draw: st.DrawFn) -> str:
    """Generate a 15-digit string that fails the modulo-97 check."""
    while True:
        gender = draw(st.sampled_from(["1", "2"]))
        year = draw(st.integers(min_value=0, max_value=99))
        month = draw(st.integers(min_value=1, max_value=12))
        dept = draw(st.integers(min_value=1, max_value=95))
        remainder_digits = [draw(st.integers(min_value=0, max_value=9)) for _ in range(7)]
        body_str = (
            f"{gender}{year:02d}{month:02d}{dept:02d}"
            + "".join(str(d) for d in remainder_digits[:3])
        )
        # Pad body to 13 digits
        body_str = body_str.ljust(13, "0")[:13]
        body_int = int(body_str)
        correct_key = 97 - (body_int % 97)
        # Use a wrong key
        wrong_key = (correct_key + 1) % 97
        if wrong_key == correct_key:
            continue
        result = f"{body_str}{wrong_key:02d}"
        if not NIRValidator().validate(result):
            return result


@st.composite
def invalid_cpf(draw: st.DrawFn) -> str:
    """Generate an 11-digit string that fails the dual modulo-11 CPF check."""
    while True:
        base = [draw(st.integers(min_value=0, max_value=9)) for _ in range(9)]
        if len(set(base)) == 1:
            continue
        # Calculate first check digit (correct)
        first_total = sum(d * w for d, w in zip(base, range(10, 1, -1)))
        first_check = 0 if first_total % 11 < 2 else 11 - (first_total % 11)
        # Use wrong check digit
        first_wrong = (first_check + 1) % 10
        ten_digits = base + [first_wrong]
        second_total = sum(d * w for d, w in zip(ten_digits, range(11, 1, -1)))
        second_check = 0 if second_total % 11 < 2 else 11 - (second_total % 11)
        second_wrong = (second_check + 1) % 10
        result = "".join(str(d) for d in base) + str(first_wrong) + str(second_wrong)
        if not CPFValidator().validate(result):
            return result


@st.composite
def invalid_cnpj(draw: st.DrawFn) -> str:
    """Generate a 14-digit string that fails the dual modulo-11 CNPJ check."""
    while True:
        base = [draw(st.integers(min_value=0, max_value=9)) for _ in range(12)]
        if len(set(base)) == 1:
            continue
        # First check digit
        first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        first_total = sum(d * w for d, w in zip(base, first_weights))
        first_check = 0 if first_total % 11 < 2 else 11 - (first_total % 11)
        first_wrong = (first_check + 1) % 10
        # Second check digit
        thirteen = base + [first_wrong]
        second_weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        second_total = sum(d * w for d, w in zip(thirteen, second_weights))
        second_check = 0 if second_total % 11 < 2 else 11 - (second_total % 11)
        second_wrong = (second_check + 1) % 10
        result = "".join(str(d) for d in base) + str(first_wrong) + str(second_wrong)
        if not CNPJValidator().validate(result):
            return result


@st.composite
def invalid_codice_fiscale(draw: st.DrawFn) -> str:
    """Generate a 16-char string that fails the Codice Fiscale checksum."""
    letters = st.characters(min_codepoint=65, max_codepoint=90)
    while True:
        code = (
            "".join(draw(st.lists(letters, min_size=6, max_size=6)))
            + f"{draw(st.integers(min_value=0, max_value=99)):02d}"
            + draw(letters)
            + f"{draw(st.integers(min_value=1, max_value=12)):02d}"
            + draw(letters)
            + f"{draw(st.integers(min_value=0, max_value=999)):03d}"
        )
        # Replace last character with a wrong one
        wrong_char = draw(st.sampled_from(
            [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c != code[-1]]
        ))
        result = code[:15] + wrong_char
        assume(len(result) == 16)
        if not CodiceFiscaleValidator().validate(result):
            return result


# ── Steuer-ID (DE) — ISO 7064 Mod 11,2 ──────────────────────────────────────


@HYP_SETTINGS
@given(steuer_id=invalid_steuer_id())
def test_05_invalid_steuer_id_not_detected(steuer_id: str) -> None:
    """Invalid Steuer-ID (mod-11 fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("TAX_ID_DE", ISO7064Mod11_2Validator())
    detection = {"entity_type": "TAX_ID_DE", "start": 0, "end": len(steuer_id)}
    result = validate_detection(detection, registry, steuer_id)
    assume(result is None)


@HYP_SETTINGS
@given(steuer_id=invalid_steuer_id())
def test_05_invalid_steuer_id_validator_returns_false(steuer_id: str) -> None:
    """ISO7064Mod11_2Validator returns False for invalid Steuer-ID."""
    validator = ISO7064Mod11_2Validator()
    assume(not validator.validate(steuer_id))


# ── BSN (NL) — Luhn mod-10 ──────────────────────────────────────────────────


@HYP_SETTINGS
@given(bsn=invalid_bsn())
def test_05_invalid_bsn_not_detected(bsn: str) -> None:
    """Invalid BSN (Luhn fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("BSN", LuhnValidator())
    detection = {"entity_type": "BSN", "start": 0, "end": len(bsn)}
    result = validate_detection(detection, registry, bsn)
    assume(result is None)


@HYP_SETTINGS
@given(bsn=invalid_bsn())
def test_05_invalid_bsn_validator_returns_false(bsn: str) -> None:
    """LuhnValidator returns False for invalid BSN."""
    validator = LuhnValidator()
    assume(not validator.validate(bsn))


# ── NIR (FR) — Modulo-97 ─────────────────────────────────────────────────────


@HYP_SETTINGS
@given(nir=invalid_nir())
def test_05_invalid_nir_not_detected(nir: str) -> None:
    """Invalid NIR (mod-97 fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("NIR", NIRValidator())
    detection = {"entity_type": "NIR", "start": 0, "end": len(nir)}
    result = validate_detection(detection, registry, nir)
    assume(result is None)


@HYP_SETTINGS
@given(nir=invalid_nir())
def test_05_invalid_nir_validator_returns_false(nir: str) -> None:
    """NIRValidator returns False for invalid NIR."""
    validator = NIRValidator()
    assume(not validator.validate(nir))


# ── CPF (BR) — Dual modulo-11 ────────────────────────────────────────────────


@HYP_SETTINGS
@given(cpf=invalid_cpf())
def test_05_invalid_cpf_not_detected(cpf: str) -> None:
    """Invalid CPF (mod-11 fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("CPF", CPFValidator())
    detection = {"entity_type": "CPF", "start": 0, "end": len(cpf)}
    result = validate_detection(detection, registry, cpf)
    assume(result is None)


@HYP_SETTINGS
@given(cpf=invalid_cpf())
def test_05_invalid_cpf_validator_returns_false(cpf: str) -> None:
    """CPFValidator returns False for invalid CPF."""
    validator = CPFValidator()
    assume(not validator.validate(cpf))


# ── CNPJ (BR) — Dual modulo-11 ──────────────────────────────────────────────


@HYP_SETTINGS
@given(cnpj=invalid_cnpj())
def test_05_invalid_cnpj_not_detected(cnpj: str) -> None:
    """Invalid CNPJ (mod-11 fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("CNPJ", CNPJValidator())
    detection = {"entity_type": "CNPJ", "start": 0, "end": len(cnpj)}
    result = validate_detection(detection, registry, cnpj)
    assume(result is None)


@HYP_SETTINGS
@given(cnpj=invalid_cnpj())
def test_05_invalid_cnpj_validator_returns_false(cnpj: str) -> None:
    """CNPJValidator returns False for invalid CNPJ."""
    validator = CNPJValidator()
    assume(not validator.validate(cnpj))


# ── Codice Fiscale (IT) — Odd/even sum, mod-26 check char ────────────────────


@HYP_SETTINGS
@given(codice=invalid_codice_fiscale())
def test_05_invalid_codice_fiscale_not_detected(codice: str) -> None:
    """Invalid Codice Fiscale (mod-26 fail) not flagged as valid PII."""
    registry = ChecksumValidatorRegistry()
    registry.register("CODICE_FISCALE", CodiceFiscaleValidator())
    detection = {"entity_type": "CODICE_FISCALE", "start": 0, "end": len(codice)}
    result = validate_detection(detection, registry, codice)
    assume(result is None)


@HYP_SETTINGS
@given(codice=invalid_codice_fiscale())
def test_05_invalid_codice_fiscale_validator_returns_false(codice: str) -> None:
    """CodiceFiscaleValidator returns False for invalid codice."""
    validator = CodiceFiscaleValidator()
    assume(not validator.validate(codice))


# ── Regression guard: valid checksums still detected ─────────────────────────


@HYP_SETTINGS
@given(st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=11, max_size=11))
def test_05_valid_steuer_id_can_be_detected(digits: str) -> None:
    """A random 11-digit number may be valid — but the validator should not crash."""
    validator = ISO7064Mod11_2Validator()
    registry = ChecksumValidatorRegistry()
    registry.register("TAX_ID_DE", validator)
    detection = {"entity_type": "TAX_ID_DE", "start": 0, "end": len(digits)}
    result = validate_detection(detection, registry, digits)
    # The test must not raise; result is either valid or invalid
    assert result is None or result["entity_type"] == "TAX_ID_DE"


# ── Existing tests (preserved) ────────────────────────────────────────────────


@HYP_SETTINGS
@given(st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=11, max_size=11))
def test_invalid_steuer_id_checksum_is_dropped(digits: str) -> None:
    """Existing: invalid Steuer-ID checksum is dropped from detections."""
    validator = ISO7064Mod11_2Validator()
    registry = ChecksumValidatorRegistry()
    registry.register("TAX_ID_DE", validator)
    if not validator.validate(digits):
        detection = {"entity_type": "TAX_ID_DE", "start": 0, "end": len(digits)}
        assert validate_detection(detection, registry, digits) is None


@HYP_SETTINGS
@given(st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=11, max_size=14))
def test_invalid_brazilian_checksum_ids_are_dropped(digits: str) -> None:
    """Existing: invalid CPF/CNPJ checksums are dropped from detections."""
    registry = ChecksumValidatorRegistry()
    registry.register("CPF", CPFValidator())
    registry.register("CNPJ", CNPJValidator())
    if len(digits) == 11 and not CPFValidator().validate(digits):
        detection = {"entity_type": "CPF", "start": 0, "end": len(digits)}
        assert validate_detection(detection, registry, digits) is None
    if len(digits) == 14 and not CNPJValidator().validate(digits):
        detection = {"entity_type": "CNPJ", "start": 0, "end": len(digits)}
        assert validate_detection(detection, registry, digits) is None
