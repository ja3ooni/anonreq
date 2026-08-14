"""Germany locale pack — checksums, golden documents, and leak tests."""

from __future__ import annotations

from anonreq.compliance.engine import PresetEngine
from anonreq.detection.regex_detector import RegexDetector
from anonreq.locale.checksum import ChecksumValidatorRegistry, validate_detection
from anonreq.locale.checksums.germany import (
    generate_iban_de,
    generate_kvnr,
    generate_personalausweis,
    generate_steuer_id,
)
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.tokenization.tokenizer import Tokenizer

STEUER_ID = generate_steuer_id("2695437180")
AUSWEIS = generate_personalausweis("L01X00T47")
KVNR = generate_kvnr("A", "12345678")
IBAN = generate_iban_de("37040044", "0532013000")
API_KEY = "sk-" + ("a" * 24)

BANK_TICKET = (
    f"Kunde Anna Schmidt, Steuer-ID {STEUER_ID}, IBAN {IBAN}. "
    f"Bitte Vorgang Az. 14 C 123/24 prüfen. E-Mail: anna.schmidt@sparkasse.de"
)
INSURANCE_CLAIM = (
    f"Schadensmeldung KVNR {KVNR}, Personalausweis {AUSWEIS}. "
    f"Police der Allianz, HRB 12345. Telefon +49 89 12345678."
)
BUERGERAMT_LETTER = (
    f"Antrag auf Meldebescheinigung. Steuerliche Identifikationsnummer {STEUER_ID}. "
    f"Rentenversicherungsnummer 15 020649 M 003. Bitte nicht an sk-leaked senden."
)
VIBE_CODING = (
    f"Deploy with OPENAI_KEY={API_KEY} and IBAN {IBAN} in the runbook."
)


def _germany_stack():
    checksum = ChecksumValidatorRegistry()
    registry = LocaleRegistry("config/locales", checksum_registry=checksum)
    negotiator = LocaleNegotiator(registry)
    merger = RecognizerMerger(registry.get("en"))
    return registry, negotiator, merger, checksum


def _detect_de(text: str) -> list[dict]:
    _registry, negotiator, merger, checksum = _germany_stack()
    bundles, _ = negotiator.negotiate("de-DE")
    merged = merger.merge(bundles)
    detector = RegexDetector()
    extra = detector.patterns_from_entity_configs(list(merged.entity_configs.values()))
    detections = detector.detect(text, extra_patterns=extra)
    validated = []
    for detection in detections:
        kept = validate_detection(detection, checksum, text)
        if kept is not None:
            config = merged.entity_configs.get(kept["entity_type"])
            kept["reversible"] = True if config is None else config.reversible
            validated.append(kept)
    return validated


def test_germany_locale_includes_national_ids() -> None:
    registry, negotiator, merger, checksum = _germany_stack()
    bundles, _ = negotiator.negotiate("de-DE")
    merged = merger.merge(bundles)
    for name in (
        "TAX_ID_DE",
        "PERSONAL_AUSWEIS",
        "KVNR",
        "IBAN_DE",
        "SVNR_DE",
        "HR_NUMBER",
        "AKTENZEICHEN",
        "API_KEY",
    ):
        assert name in merged.entity_configs, name
    assert checksum.get("TAX_ID_DE") is not None
    assert checksum.get("PERSONAL_AUSWEIS") is not None
    assert checksum.get("KVNR") is not None
    assert checksum.get("IBAN_DE") is not None
    assert registry.get("de-DE").entity_types


def test_germany_checksums_accept_generated_ids() -> None:
    _, _, _, checksum = _germany_stack()
    assert checksum.validate("TAX_ID_DE", STEUER_ID)
    assert checksum.validate("PERSONAL_AUSWEIS", AUSWEIS)
    assert checksum.validate("KVNR", KVNR)
    assert checksum.validate("IBAN_DE", IBAN)
    assert not checksum.validate("TAX_ID_DE", "00000000000")
    assert not checksum.validate("IBAN_DE", "DE00000000000000000000")


def test_germany_compliance_preset_loads() -> None:
    engine = PresetEngine("config/compliance")
    preset = engine.get_preset("germany")
    assert preset is not None
    assert "TAX_ID_DE" in preset.mandatory_entity_types
    assert "KVNR" in preset.mandatory_entity_types
    assert "IBAN_DE" in preset.requires_checksum


def _assert_no_leak(text: str, secrets: list[str]) -> None:
    detections = _detect_de(text)
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, detections)
    for secret in secrets:
        assert secret not in tokenized, f"leaked {secret!r} in {tokenized!r}"
        compact = secret.replace(" ", "")
        if compact != secret:
            assert compact not in tokenized.replace(" ", "")
    for token, original in mapping.items():
        assert original in text
        assert token.startswith("[")


def test_golden_bank_ticket_does_not_leak() -> None:
    _assert_no_leak(BANK_TICKET, [STEUER_ID, IBAN, "anna.schmidt@sparkasse.de"])
    types = {d["entity_type"] for d in _detect_de(BANK_TICKET)}
    assert "TAX_ID_DE" in types
    assert "IBAN_DE" in types
    assert "AKTENZEICHEN" in types
    assert "EMAIL_ADDRESS" in types


def test_golden_insurance_claim_does_not_leak() -> None:
    _assert_no_leak(INSURANCE_CLAIM, [KVNR, AUSWEIS])
    types = {d["entity_type"] for d in _detect_de(INSURANCE_CLAIM)}
    assert "KVNR" in types
    assert "PERSONAL_AUSWEIS" in types
    assert "HR_NUMBER" in types


def test_golden_buergeramt_letter_does_not_leak() -> None:
    _assert_no_leak(BUERGERAMT_LETTER, [STEUER_ID])
    types = {d["entity_type"] for d in _detect_de(BUERGERAMT_LETTER)}
    assert "TAX_ID_DE" in types
    assert "SVNR_DE" in types


def test_api_key_is_irreversible() -> None:
    detections = _detect_de(VIBE_CODING)
    api_dets = [d for d in detections if d["entity_type"] == "API_KEY"]
    assert api_dets
    assert all(d["reversible"] is False for d in api_dets)
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(VIBE_CODING, detections)
    assert API_KEY not in tokenized
    assert API_KEY not in mapping.values()
    assert IBAN not in tokenized
    assert any(v.replace(" ", "") == IBAN for v in mapping.values()) or IBAN in mapping.values()
