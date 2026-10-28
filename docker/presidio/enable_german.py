"""Enable German recognizers in the Presidio 2.2.354 analyzer process.

The stock image constructs ``AnalyzerEngine()``, which loads recognizers
for English only. Copying a German spaCy model is not enough: ``/analyze``
with ``language=de`` then returns HTTP 500 ("No matching recognizers").
This script patches the image's ``app.py`` at build time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

APP_PATH = Path("/usr/bin/presidio-analyzer/app.py")

_ENGINE_LINE = re.compile(r"^(\s*)self\.engine = AnalyzerEngine\(\)\s*$", re.MULTILINE)


def patch_app_source(source: str) -> str:
    """Return ``app.py`` source that loads English and German recognizers."""
    match = _ENGINE_LINE.search(source)
    if match is None:
        raise RuntimeError(
            "app.py has no `self.engine = AnalyzerEngine()` line; "
            "the base image layout changed and needs a DevOps review"
        )
    indent = match.group(1)
    replacement = (
        f"{indent}self.engine = AnalyzerEngine(supported_languages=['en', 'de'])\n"
        f"{indent}self.engine.registry.add_recognizers_from_yaml(\n"
        f"{indent}    'conf/german_recognizers.yaml'\n"
        f"{indent})\n"
    )
    return _ENGINE_LINE.sub(replacement, source, count=1)


def main(path: Path = APP_PATH) -> None:
    if not path.is_file():
        raise RuntimeError(f"Presidio app.py not found at {path}")
    updated = patch_app_source(path.read_text())
    path.write_text(updated)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else APP_PATH
    main(target)
