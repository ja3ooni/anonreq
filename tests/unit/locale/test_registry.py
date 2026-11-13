from __future__ import annotations

from pathlib import Path

from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.registry import LocaleRegistry


def test_registry_discovers_all_locale_bundles() -> None:
    registry = LocaleRegistry("config/locales")
    assert registry.list_locales() == [
        "ar",
        "bg-BG",
        "de-DE",
        "en",
        "es",
        "fr-FR",
        "it-IT",
        "nl-NL",
        "pt-BR",
    ]


def test_registry_get_is_case_insensitive() -> None:
    registry = LocaleRegistry("config/locales")
    assert registry.get("de-de").code == "de-DE"
    assert registry.get("unknown") is None


def test_registry_registers_checksum_validators() -> None:
    checksum_registry = ChecksumValidatorRegistry()
    LocaleRegistry("config/locales", checksum_registry=checksum_registry)
    assert checksum_registry.get("TAX_ID_DE") is not None
    assert checksum_registry.get("PERSONAL_AUSWEIS") is not None
    assert checksum_registry.get("KVNR") is not None
    assert checksum_registry.get("IBAN_DE") is not None
    assert checksum_registry.get("CPF") is not None
    assert checksum_registry.get("CNPJ") is not None


def test_malformed_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("not: [valid")
    registry = LocaleRegistry(str(tmp_path))
    assert registry.list_locales() == []


def test_duplicate_code_is_skipped_not_registered_twice(tmp_path: Path) -> None:
    (tmp_path / "one.yaml").write_text("code: same\nentity_types: []\n")
    (tmp_path / "two.yaml").write_text("code: same\nentity_types: []\n")
    registry = LocaleRegistry(str(tmp_path))
    assert registry.list_locales() == []


def test_bare_language_resolves_to_its_only_regional_bundle() -> None:
    registry = LocaleRegistry("config/locales")
    assert registry.get("bg").code == "bg-BG"
    assert registry.get("BG").code == "bg-BG"
    assert registry.get("bg_BG").code == "bg-BG"
    assert registry.get("de").code == "de-DE"
    # A bare bundle wins over any regional one.
    assert registry.get("en").code == "en"
    # Other regions are not guessed: de-AT may have different identifiers.
    assert registry.get("de-AT") is None
    assert registry.get("zz") is None


def test_ambiguous_bare_language_is_not_mapped(tmp_path: Path) -> None:
    for code in ("pt-BR", "pt-PT"):
        (tmp_path / f"{code}.yaml").write_text(f"code: {code}\nentity_types: []\n")
    registry = LocaleRegistry(str(tmp_path))
    assert registry.get("pt") is None
    assert registry.get("pt-PT").code == "pt-PT"
