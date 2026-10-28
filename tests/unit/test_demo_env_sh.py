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


# --- set_env_var / get_env_var / repair_glued_env --------------------------


def _sh(tmp_path: Path, script: str, env_text: str | None = None, mode: int = 0o600):
    env = tmp_path / ".env"
    if env_text is not None:
        env.write_text(env_text)
        env.chmod(mode)
    proc = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; . "{LIB}"; ENV_FILE="{env}"; {script}'],
        capture_output=True,
        text=True,
        check=True,
    )
    return env, proc


def _lines(env: Path) -> list[str]:
    return env.read_text().splitlines()


def test_append_to_env_without_trailing_newline(tmp_path):
    env, _ = _sh(
        tmp_path,
        "set_env_var PROVIDER_API_KEY xai-fake-123",
        env_text="XAI_BASE_URL=https://api.x.ai",
    )
    assert _lines(env) == ["XAI_BASE_URL=https://api.x.ai", "PROVIDER_API_KEY=xai-fake-123"]
    assert env.read_text().endswith("\n")


def test_replace_in_place_and_idempotent(tmp_path):
    start = "A=1\nPROVIDER_API_KEY=old\nB=2\nPROVIDER_API_KEY=older\n"
    script = "set_env_var PROVIDER_API_KEY new; set_env_var C 3"
    env, _ = _sh(tmp_path, script, env_text=start)
    first = env.read_text()
    assert _lines(env) == ["A=1", "PROVIDER_API_KEY=new", "B=2", "C=3"]
    _sh(tmp_path, script)
    assert env.read_text() == first


@pytest.mark.parametrize(
    "value",
    [
        "a/b&c=d+e",
        "x\\y|z#q",
        "s3cr3t$HOME`id`",
        "sqlite+aiosqlite:////app/data/anonreq.db",
        "with space and 'quotes' \"dq\"",
        "",
    ],
)
def test_special_characters_round_trip(tmp_path, value):
    env = tmp_path / ".env"
    env.write_text("K=old\n")
    proc = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; set_env_var K "$V" "{env}"; get_env_var K "{env}"'],
        capture_output=True,
        text=True,
        check=True,
        env={"V": value, "PATH": "/usr/bin:/bin"},
    )
    assert _lines(env) == [f"K={value}"]
    assert proc.stdout == value + "\n"


def test_mode_600_kept(tmp_path):
    env, _ = _sh(tmp_path, "set_env_var K v", env_text="A=1", mode=0o600)
    assert (env.stat().st_mode & 0o777) == 0o600
    _sh(tmp_path, 'repair_glued_env "$ENV_FILE"; sanitize_db_url "$ENV_FILE"')
    assert (env.stat().st_mode & 0o777) == 0o600


def test_no_temp_files_left(tmp_path):
    _sh(tmp_path, 'set_env_var K v; repair_glued_env "$ENV_FILE"', env_text="A=1\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == [".env"]


def test_glued_line_is_split_and_warned_without_value(tmp_path):
    secret = "xai-FAKE-not-a-real-key"
    env, proc = _sh(
        tmp_path,
        'repair_glued_env "$ENV_FILE"',
        env_text=f"A=1\nXAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY={secret}\nB=2\n",
    )
    assert _lines(env) == [
        "A=1",
        "XAI_BASE_URL=https://api.x.ai",
        f"PROVIDER_API_KEY={secret}",
        "B=2",
    ]
    assert "PROVIDER_API_KEY" in proc.stderr
    assert secret not in proc.stderr
    assert secret not in proc.stdout


def test_repair_leaves_normal_lines_and_comments_alone(tmp_path):
    text = (
        "# XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=x\n"
        "ANONREQ_DATABASE_URL=postgresql+asyncpg://u:p@h/db\n"
        "XAI_API_KEY=xai-abc=def\n"
    )
    env, proc = _sh(tmp_path, 'repair_glued_env "$ENV_FILE"', env_text=text)
    assert env.read_text() == text
    assert proc.stderr == ""


def test_demo_sh_has_no_raw_env_writes():
    demo = (LIB.parents[1] / "demo.sh").read_text()
    lib = LIB.read_text()
    for src in (demo, lib):
        assert '>> "$ENV_FILE"' not in src
        assert "sed -i" not in src
