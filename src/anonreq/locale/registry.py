"""Locale bundle auto-discovery and checksum validator registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from anonreq.locale.bundle import LocaleBundle
from anonreq.locale.checksum import ChecksumValidator, ChecksumValidatorRegistry
from anonreq.locale.checksums.codice_fiscale import CodiceFiscaleValidator
from anonreq.locale.checksums.germany import (
    IBANMod97Validator,
    KVNRValidator,
    PersonalausweisValidator,
)
from anonreq.locale.checksums.iso7064 import ISO7064Mod11_2Validator
from anonreq.locale.checksums.luhn import CNPJValidator, CPFValidator, LuhnValidator
from anonreq.locale.checksums.nir import NIRValidator

_VALIDATOR_FACTORIES: dict[str, type[ChecksumValidator]] = {
    "TAX_ID_DE": ISO7064Mod11_2Validator,
    "BSN": LuhnValidator,
    "NIR": NIRValidator,
    "CODICE_FISCALE": CodiceFiscaleValidator,
    "CPF": CPFValidator,
    "CNPJ": CNPJValidator,
    "PERSONAL_AUSWEIS": PersonalausweisValidator,
    "KVNR": KVNRValidator,
    "IBAN_DE": IBANMod97Validator,
}

logger = structlog.get_logger("anonreq.locale.registry")


class LocaleRegistry:
    """Discovers locale bundle YAML files from ``config/locales``."""

    def __init__(
        self,
        locales_dir: str = "config/locales",
        checksum_registry: ChecksumValidatorRegistry | None = None,
    ) -> None:
        self._locales_dir = Path(locales_dir)
        self._bundles: dict[str, LocaleBundle] = {}
        self._canonical_codes: dict[str, str] = {}
        self._load_bundles()
        if checksum_registry is not None:
            self.register_checksum_validators(checksum_registry)

    def _load_bundles(self) -> None:
        if not self._locales_dir.exists():
            logger.warning("locale_registry.dir_missing", path=str(self._locales_dir))
            return

        for path in sorted(self._locales_dir.glob("*.yaml")):
            try:
                with open(path) as f:
                    data: dict[str, Any] = yaml.safe_load(f) or {}
                bundle = LocaleBundle.from_dict(data)
                if bundle.code != path.stem:
                    raise ValueError(f"bundle code {bundle.code!r} does not match filename {path.stem!r}")  # noqa: E501
                key = bundle.code.casefold()
                if key in self._canonical_codes:
                    raise ValueError(f"duplicate locale code {bundle.code}")
                self._bundles[bundle.code] = bundle
                self._canonical_codes[key] = bundle.code
            except Exception as exc:
                logger.warning(
                    "locale_registry.bundle_skipped",
                    path=str(path),
                    error=type(exc).__name__,
                )

    def get(self, locale_code: str) -> LocaleBundle | None:
        canonical = self._canonical_codes.get(locale_code.casefold())
        if canonical is None:
            return None
        return self._bundles[canonical]

    def list_locales(self) -> list[str]:
        return sorted(self._bundles)

    def get_recognizers(self, locale_code: str) -> list[str]:
        bundle = self.get(locale_code)
        return [] if bundle is None else [et.name for et in bundle.entity_types]

    def register_checksum_validators(self, checksum_registry: ChecksumValidatorRegistry) -> None:
        for bundle in self._bundles.values():
            for checksum in bundle.all_checksums:
                validator_id = checksum.validator_id.upper()
                factory = _VALIDATOR_FACTORIES.get(validator_id)
                if factory is None:
                    continue
                checksum_registry.register(validator_id, factory())
                if validator_id == "CPF":
                    checksum_registry.register("CNPJ", CNPJValidator())
                elif validator_id == "CNPJ":
                    checksum_registry.register("CPF", CPFValidator())
