"""Map a negotiated AnonReq locale to the Presidio analyzer language code.

Presidio's ``/analyze`` API takes one ISO 639-1 language per call (``en``,
``de``). Locale bundles use that code (``en``, ``es``, ``ar``) or a BCP 47
tag (``de-DE``, ``pt-BR``). The detection stage must send the negotiated
tag's primary language; the previous default of ``en`` made the German
spaCy model unreachable for ``de-DE`` requests.
"""

from __future__ import annotations

from typing import Any

DEFAULT_PRESIDIO_LANGUAGE = "en"


def presidio_language_from_locale(locale_code: str | None) -> str:
    """Return the Presidio language for one locale code.

    Unknown or empty codes use English. A negotiated code such as ``de`` is
    never rewritten to English when the sidecar rejects it: detection fails
    closed instead of sending the text to the English model.
    """
    if locale_code is None:
        return DEFAULT_PRESIDIO_LANGUAGE
    primary = locale_code.strip().replace("_", "-").split("-", 1)[0].lower()
    if len(primary) < 2 or len(primary) > 3 or not primary.isalpha():
        return DEFAULT_PRESIDIO_LANGUAGE
    return primary


def presidio_language_from_bundles(bundles: Any) -> str:
    """Return the Presidio language for the negotiated locale list.

    Presidio accepts one language per request. The first bundle is the
    client's preference (``X-AnonReq-Locale`` order). This is not the
    merged recognizer set: that set always includes universal ``en`` and
    is sorted by code, which would send ``en`` for ``fr-FR``.
    """
    if not bundles:
        return DEFAULT_PRESIDIO_LANGUAGE
    first = bundles[0]
    code = getattr(first, "code", None)
    if not isinstance(code, str):
        return DEFAULT_PRESIDIO_LANGUAGE
    return presidio_language_from_locale(code)
