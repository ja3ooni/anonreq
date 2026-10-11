"""Database-backed tenant registry: persistence, multi-replica convergence, fail-closed."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from anonreq.middleware.tenant import TenantContextMiddleware
from anonreq.tenant.models import TenantProfile
from anonreq.tenant.registry import SeedTenantError, TenantRegistry
from anonreq.tenant.store import (
    InvalidTenantIdError,
    TenantStore,
    TenantStoreError,
    validate_tenant_id,
)

SEED_YAML = "config/tenants.yaml"  # defines the seed tenant "default"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def make_replica(
    url: str, clock: FakeClock, ttl: float = 10.0, neg_ttl: float = 5.0
) -> tuple[TenantRegistry, AsyncEngine]:
    """One gateway replica: its own engine and its own in-memory cache."""
    engine = create_async_engine(url)
    registry = TenantRegistry(
        SEED_YAML,
        store=TenantStore(engine),
        cache_ttl=ttl,
        negative_ttl=neg_ttl,
        clock=clock,
    )
    return registry, engine


def profile(tenant_id: str, **overrides: object) -> TenantProfile:
    fields: dict[str, object] = {"display_name": f"Name {tenant_id}", **overrides}
    return TenantProfile(tenant_id=tenant_id, **fields)  # type: ignore[arg-type]


@pytest.mark.unit
class TestPersistence:
    async def test_upsert_creates_then_updates(self, db_url: str) -> None:
        reg, engine = await make_replica(db_url, FakeClock())
        stored, created = await reg.upsert(profile("ws-1", allowed_models=["gpt-4o"]))
        assert created is True
        assert stored.allowed_models == ["gpt-4o"]

        stored, created = await reg.upsert(profile("ws-1", display_name="Renamed"))
        assert created is False
        assert stored.display_name == "Renamed"
        assert stored.allowed_models == []  # PUT replaces, it does not merge
        await engine.dispose()

    async def test_tenant_survives_restart(self, db_url: str) -> None:
        first, e1 = await make_replica(db_url, FakeClock())
        await first.upsert(profile("ws-restart"))
        await e1.dispose()

        second, e2 = await make_replica(db_url, FakeClock())  # fresh process, empty cache
        found = await second.aget("ws-restart")
        assert found is not None and found.display_name == "Name ws-restart"
        await e2.dispose()

    async def test_concurrent_first_upsert_yields_one_row(self, db_url: str) -> None:
        a, ea = await make_replica(db_url, FakeClock())
        b, eb = await make_replica(db_url, FakeClock())
        await asyncio.gather(a.upsert(profile("ws-race")), b.upsert(profile("ws-race")))
        rows = await a.list_with_source()
        assert [p.tenant_id for p, _ in rows].count("ws-race") == 1
        await ea.dispose()
        await eb.dispose()


@pytest.mark.unit
class TestReplicaConvergence:
    async def test_tenant_created_on_one_replica_is_visible_on_another(self, db_url: str) -> None:
        clock = FakeClock()
        a, ea = await make_replica(db_url, clock)
        b, eb = await make_replica(db_url, clock)
        assert await b.aget("ws-new") is None  # cached as a miss on replica B
        await a.upsert(profile("ws-new"))

        assert await b.aget("ws-new") is None  # still inside the negative TTL
        clock.advance(6)
        assert (await b.aget("ws-new")) is not None  # negative TTL elapsed
        await ea.dispose()
        await eb.dispose()

    async def test_disable_reaches_other_replica_within_ttl(self, db_url: str) -> None:
        clock = FakeClock()
        a, ea = await make_replica(db_url, clock, ttl=10)
        b, eb = await make_replica(db_url, clock, ttl=10)
        await a.upsert(profile("ws-off"))
        assert (await b.aget("ws-off")).enabled is True  # type: ignore[union-attr]

        await a.set_enabled("ws-off", False)
        assert (await a.aget("ws-off")).enabled is False  # type: ignore[union-attr]  # same replica: immediate
        assert (await b.aget("ws-off")).enabled is True  # type: ignore[union-attr]  # B still cached
        clock.advance(11)
        assert (await b.aget("ws-off")).enabled is False  # type: ignore[union-attr]
        await ea.dispose()
        await eb.dispose()


@pytest.mark.unit
class TestSeedAndValidation:
    async def test_seed_tenant_is_read_only(self, db_url: str) -> None:
        reg, engine = await make_replica(db_url, FakeClock())
        with pytest.raises(SeedTenantError):
            await reg.upsert(profile("default"))
        with pytest.raises(SeedTenantError):
            await reg.set_enabled("default", False)
        assert (await reg.aget("default")) is not None
        await engine.dispose()

    async def test_set_enabled_unknown_returns_none(self, db_url: str) -> None:
        reg, engine = await make_replica(db_url, FakeClock())
        assert await reg.set_enabled("nope", False) is None
        await engine.dispose()

    @pytest.mark.parametrize("bad", ["", "-x", "a b", "a/b", "x" * 65, "é"])
    def test_invalid_ids_rejected(self, bad: str) -> None:
        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id(bad)

    def test_uuid_is_a_valid_id(self) -> None:
        validate_tenant_id("0b5c3f0e-7a52-4f6b-9a83-5f1f0e0c9d11")

    async def test_registry_without_store_behaves_as_before(self) -> None:
        reg = TenantRegistry(SEED_YAML)
        assert await reg.aget("default") is not None
        assert await reg.aget("unknown") is None


@pytest.mark.unit
class TestFailClosed:
    async def test_missing_table_is_reported_at_startup(self, db_url: str) -> None:
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql("DROP TABLE tenant")
        with pytest.raises(TenantStoreError, match="alembic upgrade head"):
            await TenantStore(engine).check_schema()
        await engine.dispose()

    async def test_unreadable_database_returns_503_not_a_guess(self, unreachable_db_url: str) -> None:
        broken, engine = await make_replica(unreachable_db_url, FakeClock())
        app = FastAPI()

        @app.get("/v1/test")
        async def route(request: Request) -> dict:
            return {"tenant_id": request.state.tenant_id}

        app.add_middleware(TenantContextMiddleware, tenant_registry=broken)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            resp = await client.get("/v1/test", headers={"X-AnonReq-Tenant-ID": "ws-other"})
        assert resp.status_code == 503
        assert resp.json() == {"error": "tenant_registry_unavailable"}
        await engine.dispose()
