from __future__ import annotations

from anonreq.locale.checksum import ChecksumValidatorRegistry, validate_detection
from anonreq.locale.checksums.codice_fiscale import CodiceFiscaleValidator
from anonreq.locale.checksums.iso7064 import ISO7064Mod11_2Validator
from anonreq.locale.checksums.luhn import CNPJValidator, CPFValidator, LuhnValidator
from anonreq.locale.checksums.nir import NIRValidator


def test_luhn_validator() -> None:
    validator = LuhnValidator()
    assert validator.validate("123456782")
    assert not validator.validate("123456781")


def test_cpf_and_cnpj_validators() -> None:
    assert CPFValidator().validate("529.982.247-25")
    assert not CPFValidator().validate("529.982.247-26")
    assert CNPJValidator().validate("04.252.011/0001-10")
    assert not CNPJValidator().validate("04.252.011/0001-11")


def test_nir_validator() -> None:
    assert NIRValidator().validate("180067501234589")
    assert not NIRValidator().validate("180137501234500")
    assert not NIRValidator().validate("380067501234568")


def test_codice_fiscale_validator() -> None:
    assert CodiceFiscaleValidator().validate("RSSMRA85M01H501Q")
    assert not CodiceFiscaleValidator().validate("RSSMRA85M01H501A")


def test_iso7064_validator_accepts_generated_value() -> None:
    validator = ISO7064Mod11_2Validator()
    assert validator.validate("86095742719")
    assert not validator.validate("86095742718")


def test_registry_and_validate_detection_drop_invalid() -> None:
    registry = ChecksumValidatorRegistry()
    registry.register("CPF", CPFValidator())

    valid = {"entity_type": "CPF", "start": 0, "end": 14}
    invalid = {"entity_type": "CPF", "start": 0, "end": 14}
    assert validate_detection(valid, registry, "529.982.247-25") == valid
    assert validate_detection(invalid, registry, "529.982.247-26") is None


def test_unregistered_detection_passes_through() -> None:
    registry = ChecksumValidatorRegistry()
    detection = {"entity_type": "EMAIL_ADDRESS", "value": "a@example.com"}
    assert validate_detection(detection, registry) == detection
