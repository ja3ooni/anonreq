"""X-AnonReq-Locale parsing and resolution."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from anonreq.locale.bundle import LocaleBundle
from anonreq.locale.registry import LocaleRegistry

logger = structlog.get_logger("anonreq.locale.negotiator")


@dataclass
class HeaderParseResult:
    """Parsed locale header state."""

    locale_codes: list[str]
    was_fallback: bool = False
    dropped_codes: list[str] = field(default_factory=list)
    had_header: bool = False


class LocaleNegotiationError(Exception):
    """Raised when a single requested locale cannot be resolved."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        supported_locales: list[str] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.supported_locales = supported_locales or []
        super().__init__(self.__str__())

    def __str__(self) -> str:
        supported = ", ".join(self.supported_locales)
        return f"{self.message}. Supported locales: {supported}"


class LocaleNegotiator:
    """Parses and resolves locale headers into locale bundles."""

    def __init__(
        self,
        locale_registry: LocaleRegistry,
        universal_locale: str = "en",
    ) -> None:
        self._registry = locale_registry
        self._universal_locale = universal_locale

    def parse_header(self, header_value: str | None) -> HeaderParseResult:
        if header_value is None or not header_value.strip():
            return HeaderParseResult([], was_fallback=True, had_header=False)

        raw_entries = header_value.split(",")
        dropped: list[str] = []
        codes: list[str] = []
        for entry in raw_entries:
            code = entry.strip()
            if not code:
                dropped.append(entry)
                continue
            codes.append(code)

        if len(codes) > 10:
            dropped.extend(codes[10:])
            codes = codes[:10]
            logger.warning("locale.header_truncated", max_locales=10)

        if dropped:
            logger.warning("locale.header_entries_dropped", count=len(dropped))

        return HeaderParseResult(
            locale_codes=codes,
            dropped_codes=dropped,
            had_header=True,
        )

    def resolve_locales(self, parse_result: HeaderParseResult) -> list[LocaleBundle]:
        if not parse_result.locale_codes:
            universal = self._registry.get(self._universal_locale)
            parse_result.was_fallback = True
            return [universal] if universal else []

        resolved: list[LocaleBundle] = []
        for code in parse_result.locale_codes:
            bundle = self._registry.get(code)
            if bundle is None:
                parse_result.dropped_codes.append(code)
                logger.warning("locale.unknown_dropped", locale=code)
                continue
            resolved.append(bundle)

        if resolved:
            return resolved

        if len(parse_result.locale_codes) == 1:
            raise LocaleNegotiationError(
                f"Unsupported locale: {parse_result.locale_codes[0]}",
                supported_locales=self._registry.list_locales(),
            )

        universal = self._registry.get(self._universal_locale)
        parse_result.was_fallback = True
        return [universal] if universal else []

    def negotiate(self, header_value: str | None) -> tuple[list[LocaleBundle], HeaderParseResult]:
        parsed = self.parse_header(header_value)
        return self.resolve_locales(parsed), parsed
