"""Database fixtures that run tenant-registry tests on SQLite and on real PostgreSQL.

PostgreSQL comes from ``pgserver`` (an embedded server, no Docker needed). The schema is
created by the project's real Alembic migrations once per session, then each test gets its
own database cloned from that template, so migrations are tested and tests stay isolated.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.tenant.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pg_url(socket_dir: str, database: str) -> str:
    return f"postgresql+asyncpg://postgres@/{database}?host={socket_dir}"


async def _admin(socket_dir: str, statement: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(host=socket_dir, user="postgres", database="postgres")
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def pg_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, str]]:
    """Start PostgreSQL and run ``alembic upgrade head`` into a template database."""
    pgserver = pytest.importorskip("pgserver")
    data_dir = tmp_path_factory.mktemp("pg")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    socket_dir = str(data_dir)
    # Synchronous on purpose: this fixture can be requested from inside a running event loop
    # (via getfixturevalue in an async fixture), where asyncio.run() would raise.
    server.psql("CREATE DATABASE tpl;")

    env = {
        **os.environ,
        "ANONREQ_DATABASE_URL": _pg_url(socket_dir, "tpl"),
        # pytest's `pythonpath = ["src"]` does not reach a child process.
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"alembic upgrade head failed on PostgreSQL:\n{result.stderr[-2000:]}"
    try:
        yield socket_dir, "tpl"
    finally:
        server.cleanup()


@pytest.fixture(params=["sqlite", "postgres"])
async def db_url(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    if request.param == "sqlite":
        url = f"sqlite+aiosqlite:///{tmp_path / 'tenants.db'}"
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        return url

    socket_dir, template = request.getfixturevalue("pg_template")
    name = f"t_{uuid.uuid4().hex[:12]}"
    await _admin(socket_dir, f"CREATE DATABASE {name} TEMPLATE {template}")
    return _pg_url(socket_dir, name)


@pytest.fixture
def unreachable_db_url(db_url: str, tmp_path: Path) -> str:
    """A URL of the same dialect that cannot be connected to."""
    if db_url.startswith("sqlite"):
        return f"sqlite+aiosqlite:///{tmp_path / 'missing-dir' / 'x.db'}"
    return "postgresql+asyncpg://nobody@127.0.0.1:1/none"
