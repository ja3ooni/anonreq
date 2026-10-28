"""scripts/lib/demo_env.sh: sanitize_db_url keeps the demo DB on /app/data."""

import shutil
import subprocess
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "demo_env.sh"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _run(tmp_path: Path, content: str) -> tuple[str, str]:
    env = tmp_path / ".env"
    env.write_text(content)
    out = subprocess.run(
        ["bash", "-c", f'. "{LIB}" && sanitize_db_url "{env}"'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return env.read_text(), out


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///./anonreq.db",
        "sqlite+aiosqlite:///anonreq.db",
        "sqlite:////tmp/anonreq.db",
        '"sqlite+aiosqlite:///./anonreq.db"',
    ],
)
def test_non_volume_sqlite_url_is_commented_out(tmp_path, url):
    text, out = _run(tmp_path, f"A=1\nANONREQ_DATABASE_URL={url}\nB=2\n")
    assert "\nANONREQ_DATABASE_URL=" not in "\n" + text
    assert "# disabled by make demo" in text
    assert "A=1" in text
    assert "B=2" in text
    assert "NOTE: commented out ANONREQ_DATABASE_URL" in out


@pytest.mark.parametrize(
    "content",
    [
        "ANONREQ_DATABASE_URL=sqlite+aiosqlite:////app/data/anonreq.db\n",
        "ANONREQ_DATABASE_URL=postgresql+asyncpg://u:p@postgres:5432/anonreq\n",
        "# ANONREQ_DATABASE_URL=sqlite+aiosqlite:///./anonreq.db\n",
        "A=1\n",
    ],
)
def test_volume_postgres_commented_or_absent_untouched(tmp_path, content):
    text, out = _run(tmp_path, content)
    assert text == content
    assert out == ""


def test_idempotent(tmp_path):
    first, _ = _run(tmp_path, "ANONREQ_DATABASE_URL=sqlite+aiosqlite:///./anonreq.db\n")
    second, out = _run(tmp_path, first)
    assert second == first
    assert out == ""


def test_env_example_has_no_active_relative_sqlite_url():
    example = (LIB.parents[2] / ".env.example").read_text()
    active = [ln for ln in example.splitlines() if ln.startswith("ANONREQ_DATABASE_URL=")]
    assert active == []
