#!/usr/bin/env python3
"""Generate config/locales/bg-BG.yaml from bg-BG.yaml.tpl.

The context-word patterns (ЕГН, ЛНЧ, ЕИК, лична карта, тел. ...) need one
fixed-width lookbehind per label and separator, because Python's ``re``
does not allow variable-width lookbehind. Editing that by hand is error
prone, so edit the template or the label lists here and regenerate:

    python scripts/bg_locale/generate.py          # write the YAML
    python scripts/bg_locale/generate.py --check  # exit 1 if it is stale

``tests/unit/locale/test_bg_locale_generator.py`` runs ``--check`` logic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("bg-BG.yaml.tpl")
OUTPUT = ROOT / "config" / "locales" / "bg-BG.yaml"

SEPARATORS = [" ", ":", ": ", " : ", "№", "№ ", " №", " № ", ": №", ": № ", " - ", "-"]

EGN_LABELS = ["ЕГН", "EGN"]
LNCH_LABELS = ["ЛНЧ", "LNCh", "LNC", "личен номер на чужденец"]
EIK_LABELS = ["ЕИК", "EIK", "БУЛСТАТ", "BULSTAT", "ЕИК/БУЛСТАТ", "UIC", "ИН по ДДС", "ДДС"]
ID_LABELS = [
    "лична карта", "л\\.к\\.", "л\\. к\\.", "ЛК", "ID card", "identity card",
    "документ за самоличност",
]
PHONE_LABELS = ["тел\\.", "тел", "телефон", "моб\\.", "мобилен", "GSM"]

# Value shapes. ``END`` allows a trailing comma or full stop but not a decimal.
END = r"(?![\w/-]|[.,]\d)"
START = r"(?<![\w/+-])(?<!\d[.,])"
D10 = r"\d{10}" + END
EIK_VALUE = r"(?:BG)?\d{9}(?:\d{4})?" + END
ID_VALUE = r"(?:\d{9}|[A-ZА-Я]{2}\s?\d{7})" + END  # noqa: RUF001 - Cyrillic letters
PHONE_VALUE = r"(?:8[789]|9[89])(?:[\s.-]?\d){7}(?![\w.-]*\d)"


def context(labels: list[str]) -> str:
    """One case-insensitive fixed-width lookbehind per label and separator."""
    alternatives = [
        f"(?<=(?i:{label}){sep})" for label in labels for sep in SEPARATORS
    ]
    return "(?:" + "|".join(alternatives) + ")"


def _quote(pattern: str) -> str:
    return "'" + pattern.replace("'", "''") + "'"


def render() -> str:
    # The lookahead fails fast on non-digits before the lookbehinds run.
    patterns = {
        "EGN_CTX": START + f"(?={D10})" + context(EGN_LABELS) + D10,
        "LNCH_CTX": START + f"(?={D10})" + context(LNCH_LABELS) + D10,
        "EIK_CTX": START + f"(?={EIK_VALUE})" + context(EIK_LABELS) + EIK_VALUE,
        "ID_CTX": START + f"(?={ID_VALUE})" + context(ID_LABELS) + ID_VALUE,
        "PHONE_CTX": r"(?<![\w+./-])(?=(?:8[789]|9[89])\d)"
        + context(PHONE_LABELS)
        + PHONE_VALUE,
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, pattern in patterns.items():
        text = text.replace("{{" + key + "}}", _quote(pattern))
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the YAML is stale")
    args = parser.parse_args(argv)
    rendered = render()
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"{OUTPUT} is stale; run {Path(__file__).name}", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
