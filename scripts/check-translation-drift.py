#!/usr/bin/env python3
"""
Check translation drift between English source docs and translated docs.

For each English .md file under `docs/en/`, check whether a corresponding
translation exists under `docs/<locale>/` and whether the English source
has been modified more recently than the translation.

Usage:
    python scripts/check-translation-drift.py --docs-dir docs --locales de
    python scripts/check-translation-drift.py --docs-dir docs --locales de,fr,ja
"""

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect translation drift")
    parser.add_argument("--docs-dir", required=True, help="Root docs directory")
    parser.add_argument(
        "--locales", required=True, help="Comma-separated locale codes"
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    locales = [l.strip() for l in args.locales.split(",")]

    en_dir = docs_dir / "en"
    if not en_dir.is_dir():
        print(f"ERROR: English docs directory not found: {en_dir}")
        sys.exit(1)

    exit_code = 0

    for en_file in sorted(en_dir.rglob("*.md")):
        rel_path = en_file.relative_to(en_dir)

        for locale in locales:
            locale_file = docs_dir / locale / rel_path

            if not locale_file.is_file():
                print(
                    f"DRIFT: Missing translation for {rel_path} in {locale}/"
                )
                exit_code = 1
                continue

            en_mtime = en_file.stat().st_mtime
            locale_mtime = locale_file.stat().st_mtime

            if en_mtime > locale_mtime + 1:
                print(
                    f"DRIFT: {rel_path} (en) is newer than {locale}/ "
                    f"(en: {en_mtime:.0f}, {locale}: {locale_mtime:.0f})"
                )
                exit_code = 1

    if exit_code == 0:
        print("No translation drift detected")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
