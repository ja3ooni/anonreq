"""Database store for tenant records.

The ``tenant`` table (Alembic revision 003) is the shared source of truth for
every gateway replica. ``TenantRegistry`` keeps a short-lived in-process cache
in front of this store so the request path does not hit the database on every
call.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.tenant.models import TenantProfile, TenantRegistryModel

TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class TenantStoreError(Exception):
    """The tenant database could not be read or written. Callers must fail closed."""


class InvalidTenantIdError(ValueError):
    """The tenant id does not match ``TENANT_ID_PATTERN``."""


def validate_tenant_id(tenant_id: str) -> str:
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise InvalidTenantIdError(
            "tenant_id must be 1-64 characters: letters, digits, '_' or '-', "
            "starting with a letter or digit"
        )
    return tenant_id


class TenantStore:
    """Async CRUD over the ``tenant`` table."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def check_schema(self) -> None:
        """Raise ``TenantStoreError`` if the ``tenant`` table is missing.

        The gateway refuses to start rather than silently running with an empty
        registry. Fix: ``alembic upgrade head``.
        """
        try:
            async with self._sessions() as session:
                await session.execute(select(TenantRegistryModel.id).limit(1))
        except (SQLAlchemyError, OSError) as exc:
            raise TenantStoreError(
                "tenant table is not readable; run 'alembic upgrade head'"
            ) from exc

    async def get(self, tenant_id: str) -> TenantProfile | None:
        try:
            async with self._sessions() as session:
                row = await self._fetch(session, tenant_id)
                return row.to_profile() if row else None
        except (SQLAlchemyError, OSError) as exc:
            raise TenantStoreError("tenant lookup failed") from exc

    async def list_all(self) -> list[TenantProfile]:
        try:
            async with self._sessions() as session:
                result = await session.execute(
                    select(TenantRegistryModel).order_by(TenantRegistryModel.tenant_id)
                )
                return [row.to_profile() for row in result.scalars().all()]
        except (SQLAlchemyError, OSError) as exc:
            raise TenantStoreError("tenant listing failed") from exc

    async def upsert(self, profile: TenantProfile) -> tuple[TenantProfile, bool]:
        """Insert or update by ``tenant_id``. Returns ``(stored, created)``.

        Idempotent: repeating the same call leaves the same row. A concurrent
        first insert from another replica is handled by retrying as an update.
        """
        validate_tenant_id(profile.tenant_id)
        for attempt in range(2):
            try:
                return await self._upsert_once(profile)
            except IntegrityError as exc:
                if attempt == 1:
                    raise TenantStoreError("tenant upsert conflicted twice") from exc
            except (SQLAlchemyError, OSError) as exc:
                raise TenantStoreError("tenant upsert failed") from exc
        raise TenantStoreError("tenant upsert failed")  # pragma: no cover

    async def set_enabled(self, tenant_id: str, enabled: bool) -> TenantProfile | None:
        try:
            async with self._sessions() as session, session.begin():
                row = await self._fetch(session, tenant_id)
                if row is None:
                    return None
                row.enabled = enabled
                row.updated_at = datetime.now(UTC)
                return row.to_profile()
        except (SQLAlchemyError, OSError) as exc:
            raise TenantStoreError("tenant update failed") from exc

    async def _upsert_once(self, profile: TenantProfile) -> tuple[TenantProfile, bool]:
        async with self._sessions() as session, session.begin():
            row = await self._fetch(session, profile.tenant_id)
            now = datetime.now(UTC)
            if row is None:
                fresh = TenantRegistryModel.from_model(
                    TenantProfile(
                        tenant_id=profile.tenant_id,
                        display_name=profile.display_name,
                        enabled=profile.enabled,
                        kms_key_arn=profile.kms_key_arn,
                        spend_limits=profile.spend_limits,
                        rate_limits=profile.rate_limits,
                        allowed_providers=profile.allowed_providers,
                        allowed_models=profile.allowed_models,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.add(fresh)
                await session.flush()
                return fresh.to_profile(), True
            replacement = TenantRegistryModel.from_model(profile)
            row.display_name = replacement.display_name
            row.enabled = replacement.enabled
            row.kms_key_arn = replacement.kms_key_arn
            row.spend_limits_json = replacement.spend_limits_json
            row.rate_limits_json = replacement.rate_limits_json
            row.allowed_providers_json = replacement.allowed_providers_json
            row.allowed_models_json = replacement.allowed_models_json
            row.updated_at = now
            return row.to_profile(), False

    @staticmethod
    async def _fetch(session: AsyncSession, tenant_id: str) -> TenantRegistryModel | None:
        result = await session.execute(
            select(TenantRegistryModel).where(TenantRegistryModel.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()
