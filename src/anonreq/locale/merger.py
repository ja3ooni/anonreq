"""Locale recognizer merge logic."""

from __future__ import annotations

from dataclasses import dataclass

from anonreq.locale.bundle import EntityTypeConfig, LocaleBundle


@dataclass(frozen=True)
class MergedRecognizerSet:
    """Recognizer configs after universal + locale-specific merge."""

    entity_configs: dict[str, EntityTypeConfig]
    source_locales: list[str]
    has_universal: bool = True


class RecognizerMerger:
    """Merges locale recognizer bundles before detection."""

    def __init__(self, universal_bundle: LocaleBundle) -> None:
        self._universal = universal_bundle

    def merge(self, locale_bundles: list[LocaleBundle]) -> MergedRecognizerSet:
        merged: dict[str, EntityTypeConfig] = {}
        for config in sorted(self._universal.entity_types, key=lambda item: item.name):
            merged[config.name] = config

        source_codes = {self._universal.code}
        for bundle in sorted(locale_bundles, key=lambda item: item.code):
            source_codes.add(bundle.code)
            for config in sorted(bundle.entity_types, key=lambda item: item.name):
                existing = merged.get(config.name)
                if existing is None:
                    merged[config.name] = config
                elif config.confidence_threshold > existing.confidence_threshold:
                    merged[config.name] = config

        return MergedRecognizerSet(
            entity_configs=merged,
            source_locales=sorted(source_codes),
            has_universal=True,
        )
