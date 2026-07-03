#!/usr/bin/env python3
"""
Seed or update translated documentation from English source files.

For each English .md file under `docs/en/`, this script creates or updates
a corresponding translation under `docs/<locale>/` using a header-based
approach that preserves frontmatter YAML and writes a placeholder notice.

Usage:
    python scripts/translate-docs.py --docs-dir docs --locale de
    python scripts/translate-docs.py --docs-dir docs --locale de --dry-run
"""

import argparse
import os
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed translated documentation files"
    )
    parser.add_argument("--docs-dir", required=True, help="Root docs directory")
    parser.add_argument(
        "--locale", required=True, help="Target locale code (e.g., de, fr)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    en_dir = docs_dir / "en"
    locale_dir = docs_dir / args.locale
    locale_name = {"de": "German"}.get(args.locale, args.locale.upper())

    if not en_dir.is_dir():
        print(f"ERROR: English docs directory not found: {en_dir}")
        return

    if not args.dry_run:
        locale_dir.mkdir(parents=True, exist_ok=True)

    for en_file in sorted(en_dir.rglob("*.md")):
        rel_path = en_file.relative_to(en_dir)
        locale_file = locale_dir / rel_path

        if args.dry_run:
            if locale_file.exists():
                print(f"WOULD update: {locale_file}")
            else:
                print(f"WOULD create: {locale_file}")
            continue

        if locale_file.exists():
            en_mtime = en_file.stat().st_mtime
            locale_mtime = locale_file.stat().st_mtime
            if en_mtime <= locale_mtime + 1:
                continue

        locale_file.parent.mkdir(parents=True, exist_ok=True)

        content = en_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        frontmatter_end = 0
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    frontmatter_end = i + 1
                    break

        header_lines = []
        body_lines = lines[frontmatter_end:] if frontmatter_end > 0 else lines

        for i, line in enumerate(body_lines):
            if line.startswith("#") and not line.startswith("##"):
                header_lines = [line]
                break

        header = header_lines[0] if header_lines else f"# {rel_path.stem}"

        out = []
        if frontmatter_end > 0:
            out.extend(lines[:frontmatter_end])
            out.append("")
        out.append(f"> translated from en/{rel_path.as_posix()}")
        out.append("")
        out.append(header)
        out.append("")
        out.append(
            f"*Diese Dokumentation ist eine Übersetzung des englischen "
            f"Originals. Bei Abweichungen ist die englische Version "
            f"maßgeblich.*"
        )
        out.append("")
        out.append("")
        out.append(
            f"<!-- TODO: Translate this document to {locale_name} -->"
        )
        out.append("")

        locale_file.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"Created/updated: {locale_file}")

    print(f"\nDone. {args.locale}/ translations are seeded.")


if __name__ == "__main__":
    main()
