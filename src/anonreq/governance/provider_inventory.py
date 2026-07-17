"""Third-party provider inventory with DORA ICT risk flagging.

Provides:
- ``ProviderInventory``: CRUD, suspend/unsuspend, concentration risk
- DORA ICT critical designation and concentration risk management
- Integration with Phase 14 ``LifecycleService`` for stage management
- ``check_provider_active`` for ForwardingGuard integration
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.governance import ProviderAnonReqModel, ProviderRecord


class ProviderInventory:
    """Third-party provider inventory with DORA ICT risk management.

    Manages provider records per DORA ICT requirements, supporting
    suspension, concentration risk flagging, and lifecycle integration.

    Args:
        db: Async SQLAlchemy session for PostgreSQL storage.
        lifecycle_manager: Phase 14 LifecycleService for stage transitions.
    """

    def __init__(self, db: AsyncSession, lifecycle_manager: Any) -> None:
        """Initialise provider inventory.

        Args:
            db: Async SQLAlchemy session for PostgreSQL storage.
            lifecycle_manager: Phase 14 LifecycleService (or compatible) for
                stage management. Must provide ``get_current_stage`` method.
        """
        self._db = db
        self._lifecycle = lifecycle_manager

    async def create_provider_record(
        self,
        name: str,
        provider_type: str,
        dora_ict_critical: bool = False,
    ) -> ProviderRecord:
        """Create a provider record with lifecycle integration.

        Creates a provider record in PostgreSQL and initialises its
        lifecycle stage via the Phase 14 LifecycleService.

        Args:
            name: Provider name (e.g. 'OpenAI', 'Anthropic').
            provider_type: Provider type (e.g. 'llm', 'embedding').
            dora_ict_critical: Whether this is a DORA ICT critical provider.

        Returns:
            The created ProviderRecord.
        """
        now = datetime.now(UTC)
        provider_id = f"prov_{uuid.uuid4().hex[:24]}"

        # Initialise lifecycle — LifecycleService defaults to DESIGN
        await self._lifecycle.get_current_stage(provider_id)

        orm = ProviderAnonReqModel(
            provider_id=provider_id,
            name=name,
            provider_type=provider_type,
            status="active",
            lifecycle_object_id=provider_id,
            dora_ict_critical=dora_ict_critical,
            concentration_risk=False,
            review_cycle_days=365,
            created_at=now,
            updated_at=now,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)

        return _orm_to_provider_record(orm)

    async def get_provider_record(self, provider_id: str) -> ProviderRecord | None:
        """Retrieve a provider record by its ID.

        Args:
            provider_id: The provider's unique identifier.

        Returns:
            ProviderRecord or None if not found.
        """
        stmt = select(ProviderAnonReqModel).where(
            ProviderAnonReqModel.provider_id == provider_id
        )
        result = await self._db.execute(stmt)
        orm = result.scalars().unique().one_or_none()
        if orm is None:
            return None
        return _orm_to_provider_record(orm)

    async def list_providers(
        self,
        status: str | None = None,
        concentration_risk: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ProviderRecord]:
        """List provider records with optional filtering.

        Args:
            status: Optional filter by status (e.g. 'active', 'suspended').
            concentration_risk: Optional filter by concentration risk flag.
            skip: Number of records to skip (pagination).
            limit: Maximum records to return.

        Returns:
            List of ProviderRecord objects.
        """
        stmt = select(ProviderAnonReqModel)

        conditions = []
        if status is not None:
            conditions.append(ProviderAnonReqModel.status == status)
        if concentration_risk is not None:
            conditions.append(
                ProviderAnonReqModel.concentration_risk == concentration_risk
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = (
            stmt.offset(skip)
            .limit(limit)
            .order_by(ProviderAnonReqModel.created_at.desc())
        )
        result = await self._db.execute(stmt)
        orms = result.scalars().unique().all()
        return [_orm_to_provider_record(o) for o in orms]

    async def suspend_provider(
        self,
        provider_id: str,
        reason: str,  # noqa: ARG002
        suspended_by: str,  # noqa: ARG002
    ) -> ProviderRecord:
        """Suspend a provider, blocking all traffic.

        Per D-011: provider suspension immediately stops all traffic to
        the provider. Sets status to 'suspended' and emits audit event.

        Args:
            provider_id: The provider's unique identifier.
            reason: Reason for suspension.
            suspended_by: Identity of the admin performing suspension.

        Returns:
            Updated ProviderRecord.

        Raises:
            ValueError: If provider not found.
        """
        orm = await self._get_orm(provider_id)
        if orm is None:
            raise ValueError(f"Provider not found: {provider_id}")

        now = datetime.now(UTC)
        orm.status = "suspended"
        orm.updated_at = now

        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_provider_record(orm)

    async def unsuspend_provider(
        self,
        provider_id: str,
        unsuspended_by: str,  # noqa: ARG002
    ) -> ProviderRecord:
        """Unsuspend a provider, restoring traffic.

        Per D-011: sets status back to 'active' and emits audit event.

        Args:
            provider_id: The provider's unique identifier.
            unsuspended_by: Identity of the admin performing unsuspension.

        Returns:
            Updated ProviderRecord.

        Raises:
            ValueError: If provider not found.
        """
        orm = await self._get_orm(provider_id)
        if orm is None:
            raise ValueError(f"Provider not found: {provider_id}")

        now = datetime.now(UTC)
        orm.status = "active"
        orm.updated_at = now

        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_provider_record(orm)

    async def flag_concentration_risk(
        self,
        provider_id: str,
        justification: str,
    ) -> ProviderRecord:
        """Flag a provider for concentration risk.

        Per D-012: sets concentration_risk=True, stores justification,
        and sets next_review_date to 1 year from now for annual review.

        Args:
            provider_id: The provider's unique identifier.
            justification: Reason for concentration risk flagging.

        Returns:
            Updated ProviderRecord.

        Raises:
            ValueError: If provider not found.
        """
        orm = await self._get_orm(provider_id)
        if orm is None:
            raise ValueError(f"Provider not found: {provider_id}")

        now = datetime.now(UTC)
        orm.concentration_risk = True
        orm.concentration_risk_justification = justification
        orm.concentration_risk_justification_date = now
        orm.last_review_date = now
        orm.next_review_date = (now + timedelta(days=365)).replace(microsecond=0)
        orm.updated_at = now

        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_provider_record(orm)

    async def is_provider_active(self, provider_id: str) -> bool:
        """Check if a provider is active (not suspended).

        Returns True only if the provider exists and status is 'active'.
        Unknown providers return False (fail-secure).

        Args:
            provider_id: The provider's unique identifier.

        Returns:
            True if provider exists and is active, False otherwise.
        """
        record = await self.get_provider_record(provider_id)
        if record is None:
            return False
        return record.status == "active"

    async def check_provider_active(self, provider_id: str) -> None:
        """Check if a provider is active, raising if not.

        Used by ForwardingGuard. Raises an exception if the provider
        is suspended or unknown (fail-secure).

        Args:
            provider_id: The provider's unique identifier.

        Raises:
            ValueError: If provider is suspended or not found.
        """
        if not await self.is_provider_active(provider_id):
            raise ValueError(f"Provider is not active: {provider_id}")

    async def _get_orm(self, provider_id: str) -> ProviderAnonReqModel | None:
        """Get ORM model by provider_id, or None."""
        stmt = select(ProviderAnonReqModel).where(
            ProviderAnonReqModel.provider_id == provider_id
        )
        result = await self._db.execute(stmt)
        return result.scalars().unique().one_or_none()


def _orm_to_provider_record(orm: ProviderAnonReqModel) -> ProviderRecord:
    """Convert ORM model to Pydantic ProviderRecord."""
    return ProviderRecord(
        id=orm.provider_id,
        name=orm.name,
        provider_type=orm.provider_type,
        status=orm.status,
        lifecycle_object_id=orm.lifecycle_object_id,
        dora_ict_critical=orm.dora_ict_critical,
        concentration_risk=orm.concentration_risk,
        concentration_risk_justification=orm.concentration_risk_justification,
        concentration_risk_justification_date=_ensure_tz(
            orm.concentration_risk_justification_date
        ),
        contract_end_date=_ensure_tz(orm.contract_end_date),
        review_cycle_days=orm.review_cycle_days,
        last_review_date=_ensure_tz(orm.last_review_date),
        next_review_date=_ensure_tz(orm.next_review_date),
        created_at=_ensure_tz(orm.created_at),
        updated_at=_ensure_tz(orm.updated_at),
    )


def _ensure_tz(dt: Any) -> Any:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
