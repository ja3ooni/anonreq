"""Download pinned spaCy wheels using their canonical filenames.

pip refuses a wheel whose filename is not
``{distribution}-{version}-{python}-{abi}-{platform}.whl``. Build args are
read from the environment so a quoted shell heredoc cannot leave them
unexpanded.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from collections.abc import Mapping
from pathlib import Path

WHEEL_PAIRS = (
    ("EN_CORE_WEB_LG_URL", "EN_CORE_WEB_LG_SHA256"),
    ("DE_CORE_NEWS_LG_URL", "DE_CORE_NEWS_LG_SHA256"),
)


def canonical_wheel_name(url: str) -> str:
    """Return the wheel filename pip will accept for this URL."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if not name.endswith(".whl"):
        raise ValueError(f"not a wheel URL: {url}")
    stem_parts = name[: -len(".whl")].split("-")
    if len(stem_parts) != 5 or any(not part for part in stem_parts):
        raise ValueError(f"wheel filename is not canonical: {name}")
    return name


def download_plan(environ: Mapping[str, str], dest_dir: Path) -> list[tuple[str, str, Path]]:
    """Resolve URL, sha256, and canonical destination for each configured wheel."""
    plan: list[tuple[str, str, Path]] = []
    for url_key, sha_key in WHEEL_PAIRS:
        url = environ.get(url_key, "").strip()
        digest = environ.get(sha_key, "").strip().lower()
        if not url or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"{url_key} and {sha_key} must be a URL and a sha256 hex digest")
        plan.append((url, digest, dest_dir / canonical_wheel_name(url)))
    return plan


def fetch_wheel(url: str, expected_sha256: str, dest: Path) -> None:
    """Stream ``url`` to ``dest`` and delete the file if the sha256 does not match."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=300) as response, dest.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
        actual = digest.hexdigest()
        if actual != expected_sha256.lower():
            raise ValueError(f"sha256 mismatch for {dest.name}: {actual}")
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def main() -> None:
    dest_dir = Path(os.environ.get("WHEEL_DEST", "/tmp"))
    for url, digest, dest in download_plan(os.environ, dest_dir):
        fetch_wheel(url, digest, dest)


if __name__ == "__main__":
    main()
