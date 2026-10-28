"""Choose which Presidio language codes a request may send.

Presidio accepts one ISO 639-1 language per ``/analyze`` call. Locale bundles
use that code (``en``, ``es``, ``ar``) or a BCP 47 tag (``de-DE``, ``fr-FR``).
Only languages listed in ``ANONREQ_PRESIDIO_LANGUAGES`` are sent. Anything else
is analyzed as English. A language that is configured and then rejected by the
analyzer is not rewritten to English: detection fails closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DEFAULT_PRESIDIO_LANGUAGE = "en"
_LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}$")
_LOCALE_LABEL = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2})?$", re.IGNORECASE)


@dataclass(frozen=True)
class PresidioLanguagePlan:
    """Languages to send, and negotiated locales that were not allowlisted."""

    languages: tuple[str, ...]
    unsupported_locales: tuple[str, ...]


def presidio_language_from_locale(locale_code: str | None) -> str:
    """Map one locale tag to an ISO 639-1 code.

    This does not apply the deployment allowlist. Call
    ``plan_presidio_languages`` before sending the code to Presidio.
    """
    if locale_code is None:
        return DEFAULT_PRESIDIO_LANGUAGE
    primary = locale_code.strip().replace("_", "-").split("-", 1)[0].lower()
    if not _LANGUAGE_CODE.fullmatch(primary):
        return DEFAULT_PRESIDIO_LANGUAGE
    return primary


def parse_presidio_languages(value: str | None) -> tuple[str, ...]:
    """Parse ``ANONREQ_PRESIDIO_LANGUAGES`` into a stable, de-duplicated tuple.

    Empty input is English. A token that is not a 2-3 letter code raises
    ``ValueError`` so a bad deployment fails at startup instead of guessing.
    """
    if value is None or not str(value).strip():
        return (DEFAULT_PRESIDIO_LANGUAGE,)
    seen: list[str] = []
    for raw in str(value).split(","):
        token = raw.strip()
        if not token:
            continue
        primary = token.replace("_", "-").split("-", 1)[0].lower()
        if not _LANGUAGE_CODE.fullmatch(primary):
            raise ValueError(f"Invalid ANONREQ_PRESIDIO_LANGUAGES entry: {token!r}")
        if primary not in seen:
            seen.append(primary)
    return tuple(seen) if seen else (DEFAULT_PRESIDIO_LANGUAGE,)


def languages_to_probe(configured: tuple[str, ...]) -> tuple[str, ...]:
    """Languages startup must verify, including English as the fallback."""
    seen: list[str] = []
    for language in (*configured, DEFAULT_PRESIDIO_LANGUAGE):
        if language not in seen:
            seen.append(language)
    return tuple(seen)


def locale_metric_label(locale_code: str) -> str:
    """Bound the unsupported-locale metric label to a locale tag."""
    if _LOCALE_LABEL.fullmatch(locale_code):
        return locale_code
    return "invalid"


def plan_presidio_languages(
    bundles: Any,
    allowlist: tuple[str, ...] | list[str] | set[str],
) -> PresidioLanguagePlan:
    """Choose a Presidio language for every negotiated bundle.

    Bundles whose language is on the allowlist are sent as that language.
    Bundles outside the allowlist are recorded and analyzed as English.
    Order follows the locale header, not the sorted merge set, and later
    bundles are not dropped after the first one.
    """
    allowed = {language.lower() for language in allowlist}
    languages: list[str] = []
    unsupported: list[str] = []
    items = list(bundles or [])
    if not items:
        return PresidioLanguagePlan((DEFAULT_PRESIDIO_LANGUAGE,), ())

    for bundle in items:
        code = getattr(bundle, "code", None)
        locale_code = code if isinstance(code, str) and code.strip() else ""
        language = presidio_language_from_locale(locale_code or None)
        if language in allowed:
            if language not in languages:
                languages.append(language)
            continue
        label = locale_metric_label(locale_code or language)
        if label not in unsupported:
            unsupported.append(label)
        if DEFAULT_PRESIDIO_LANGUAGE not in languages:
            languages.append(DEFAULT_PRESIDIO_LANGUAGE)

    if not languages:
        languages.append(DEFAULT_PRESIDIO_LANGUAGE)
    return PresidioLanguagePlan(tuple(languages), tuple(unsupported))
