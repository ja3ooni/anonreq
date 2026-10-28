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


# --- full demo.sh run with a stub docker: no secrets in output, no rotation --

_REPO = LIB.parents[2]
_SECRET_KEYS = (
    "ANONREQ_API_KEY",
    "ANONREQ_ADMIN_API_KEY",
    "ANONREQ_KMS_MASTER_KEY",
    "ANONREQ_ANCHOR_SIGNING_KEY",
    "MINIO_ROOT_PASSWORD",
    "POSTGRES_PASSWORD",
    "XAI_API_KEY",
    "PROVIDER_API_KEY",
)
_FAKE_XAI = "xai-FAKE-test-key-0123456789abcdef"


def _demo_tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts" / "lib").mkdir(parents=True)
    shutil.copy(_REPO / "scripts" / "demo.sh", root / "scripts" / "demo.sh")
    shutil.copy(LIB, root / "scripts" / "lib" / "demo_env.sh")
    shutil.copy(_REPO / ".env.example", root / ".env")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    # info -> 8 GiB; every compose subcommand succeeds silently.
    docker.write_text('#!/bin/sh\nif [ "$1" = info ]; then echo 8589934592; fi\nexit 0\n')
    docker.chmod(0o755)
    return root


def _run_demo(root: Path, bindir: Path) -> str:
    proc = subprocess.run(
        ["bash", str(root / "scripts" / "demo.sh")],
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": f"{bindir}:/usr/local/bin:/usr/bin:/bin",
            "XAI_API_KEY": _FAKE_XAI,
            "HOME": str(root),
        },
    )
    return proc.stdout + proc.stderr


def _env_values(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (root / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k] = v
    return out


@pytest.mark.skipif(shutil.which("python3") is None, reason="python3 required")
def test_demo_sh_never_prints_secrets_and_does_not_rotate(tmp_path):
    root = _demo_tree(tmp_path)
    bindir = tmp_path / "bin"
    out1 = _run_demo(root, bindir)
    vals1 = _env_values(root)
    for key in _SECRET_KEYS:
        value = vals1.get(key, "")
        assert len(value) >= 16, key
        assert value not in out1, f"{key} value leaked into demo.sh output"
    assert "Try: curl" in out1
    assert "export ANONREQ_API_KEY=" in out1

    out2 = _run_demo(root, bindir)
    vals2 = _env_values(root)
    for key in _SECRET_KEYS:
        assert vals2[key] == vals1[key], f"{key} was rotated on re-run"
        assert vals2[key] not in out2

    # The printed export lines load exactly the .env values (CRLF-safe).
    exports = "\n".join(
        ln.strip() for ln in out2.splitlines() if ln.strip().startswith("export ANONREQ_")
    )
    env_file = root / ".env"
    env_file.write_text(env_file.read_text().replace("\n", "\r\n"))
    loaded = subprocess.run(
        ["bash", "-c", exports + '\nprintf "%s\\n%s" "$ANONREQ_API_KEY" "$ANONREQ_ADMIN_API_KEY"'],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert loaded == f"{vals1['ANONREQ_API_KEY']}\n{vals1['ANONREQ_ADMIN_API_KEY']}"


@pytest.mark.skipif(shutil.which("python3") is None, reason="python3 required")
def test_deleting_key_line_rotates_only_that_key(tmp_path):
    root = _demo_tree(tmp_path)
    bindir = tmp_path / "bin"
    _run_demo(root, bindir)
    before = _env_values(root)
    env_file = root / ".env"
    env_file.write_text(
        "\n".join(
            ln for ln in env_file.read_text().splitlines() if not ln.startswith("ANONREQ_API_KEY=")
        )
        + "\n"
    )
    _run_demo(root, bindir)
    after = _env_values(root)
    assert after["ANONREQ_API_KEY"] != before["ANONREQ_API_KEY"]
    assert after["ANONREQ_ADMIN_API_KEY"] == before["ANONREQ_ADMIN_API_KEY"]
    assert after["ANONREQ_KMS_MASTER_KEY"] == before["ANONREQ_KMS_MASTER_KEY"]


# --- review of 22d2836: no false splits, export prefix ---------------------


@pytest.mark.parametrize(
    "line",
    [
        "URL=https://h/?ANONREQ_FOO=1",
        "URL=https://h/?ANONREQ_API_KEY=1",
        "ANONREQ_DATABASE_URL=postgresql://u:p@h/db?POSTGRES_OPT=1",
        "ANONREQ_DATABASE_URL=postgresql://u:p@h/db?a=1&POSTGRES_PASSWORD=x",
        "X=a;MINIO_ROOT_USER=b",
        "X=MY_PROVIDER_API_KEY=abc",
        'X="https://api.x.aiPROVIDER_API_KEY=quoted"',
        "X='https://api.x.aiPROVIDER_API_KEY=quoted'",
        "XAI_BASE_URL=https://api.x.aiXAI_BASE_URL=unmanaged",
        "# XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=x",
    ],
)
def test_repair_does_not_split_valid_values(tmp_path, line):
    env, proc = _sh(tmp_path, 'repair_glued_env "$ENV_FILE"', env_text=line + "\n")
    assert env.read_text() == line + "\n"
    assert proc.stderr == ""


@pytest.mark.parametrize(
    ("glued", "expected"),
    [
        (
            "XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=xai-FAKE",
            ["XAI_BASE_URL=https://api.x.ai", "PROVIDER_API_KEY=xai-FAKE"],
        ),
        (
            "ANONREQ_API_KEY=abcXYZ9POSTGRES_USER=anonreqMINIO_ROOT_PASSWORD=pw",
            ["ANONREQ_API_KEY=abcXYZ9", "POSTGRES_USER=anonreq", "MINIO_ROOT_PASSWORD=pw"],
        ),
        (
            "export XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=xai-FAKE",
            ["export XAI_BASE_URL=https://api.x.ai", "PROVIDER_API_KEY=xai-FAKE"],
        ),
    ],
)
def test_repair_still_splits_real_glued_lines(tmp_path, glued, expected):
    env, proc = _sh(tmp_path, 'repair_glued_env "$ENV_FILE"', env_text=glued)
    assert _lines(env) == expected
    assert "xai-FAKE" not in proc.stderr
    assert "WARNING" in proc.stderr


def test_set_and_get_handle_export_prefix(tmp_path):
    env, proc = _sh(
        tmp_path,
        "get_env_var ANONREQ_API_KEY; set_env_var ANONREQ_API_KEY new; get_env_var ANONREQ_API_KEY",
        env_text="A=1\n  export ANONREQ_API_KEY=old\nB=2\n",
    )
    assert proc.stdout == "old\nnew\n"
    assert _lines(env) == ["A=1", "export ANONREQ_API_KEY=new", "B=2"]


def test_sanitizer_handles_export_prefix(tmp_path):
    env, proc = _sh(
        tmp_path,
        'sanitize_db_url "$ENV_FILE"',
        env_text="export ANONREQ_DATABASE_URL=sqlite+aiosqlite:///./anonreq.db\n",
    )
    assert env.read_text().startswith("# disabled by make demo")
    assert "\nexport ANONREQ_DATABASE_URL" not in "\n" + env.read_text()
    assert "NOTE" in proc.stdout


def test_printed_export_hint_handles_export_prefix_and_crlf(tmp_path):
    demo = (LIB.parents[1] / "demo.sh").read_text()
    hint = "\n".join(
        ln.strip() for ln in demo.splitlines() if ln.strip().startswith("export ANONREQ_")
    )
    assert hint.count("export ANONREQ_") == 2
    (tmp_path / ".env").write_text(
        "export ANONREQ_API_KEY=gw-val=x\r\nANONREQ_ADMIN_API_KEY=adm+/val\r\n"
    )
    out = subprocess.run(
        ["bash", "-c", hint + '\nprintf "%s|%s" "$ANONREQ_API_KEY" "$ANONREQ_ADMIN_API_KEY"'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out == "gw-val=x|adm+/val"
