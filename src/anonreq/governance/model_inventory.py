"""Model inventory with Phase 14 lifecycle integration (SR 11-7).

Provides:
- ``ModelInventory``: CRUD and approval checks for model records
- Integration with ``LifecycleService`` for stage management
- Fail-secure defaults: unknown models return not-approved
- SR 11-7 alignment documentation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.governance import (
    ModelAnonReqModel,
    ModelRecord,
    ModelRiskClassification,
)


class ModelInventory:
    """Model inventory with lifecycle integration and approval gating.

    Manages model records per SR 11-7 requirements, integrating with
    Phase 14 LifecycleService for stage management.

    Args:
        db: Async SQLAlchemy session for PostgreSQL storage.
        lifecycle_manager: Phase 14 LifecycleService for stage transitions.
    """

    def __init__(self, db: AsyncSession, lifecycle_manager: Any) -> None:
        """Initialise model inventory.

        Args:
            db: Async SQLAlchemy session for PostgreSQL storage.
            lifecycle_manager: Phase 14 LifecycleService (or compatible) for
                stage management. Must provide ``get_current_stage`` method.
        """
        self._db = db
        self._lifecycle = lifecycle_manager

    async def create_model_record(
        self,
        provider: str,
        model_name: str,
        risk_classification: ModelRiskClassification,
        documentation_url: str | None = None,
    ) -> ModelRecord:
        """Create a model record with lifecycle integration.

        Creates a model record in PostgreSQL and initialises its
        lifecycle stage via the Phase 14 LifecycleService.

        Args:
            provider: Provider name (e.g. 'openai', 'anthropic').
            model_name: Model identifier (e.g. 'gpt-4').
            risk_classification: SR 11-7 risk classification.
            documentation_url: Optional URL to model documentation.

        Returns:
            The created ModelRecord.
        """
        now = datetime.now(timezone.utc)
        model_id = f"model_{uuid.uuid4().hex[:24]}"

        # Initialise lifecycle — LifecycleService defaults to DESIGN
        stage = await self._lifecycle.get_current_stage(model_id)

        orm = ModelAnonReqModel(
            model_id=model_id,
            provider=provider,
            model_name=model_name,
            risk_classification=risk_classification.value,
            approval_status="pending",
            current_stage=stage.value.upper(),
            lifecycle_object_id=model_id,
            version="1.0.0",
            documentation_url=documentation_url,
            review_cycle_days=365,
            created_at=now,
            updated_at=now,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)

        return _orm_to_model_record(orm)

    async def get_model_record(self, model_id: str) -> ModelRecord | None:
        """Retrieve a model record by its ID.

        Args:
            model_id: The model's unique identifier.

        Returns:
            ModelRecord or None if not found.
        """
        stmt = select(ModelAnonReqModel).where(ModelAnonReqModel.model_id == model_id)
        result = await self._db.execute(stmt)
        orm = result.scalars().unique().one_or_none()
        if orm is None:
            return None
        return _orm_to_model_record(orm)

    async def get_model_record_by_name(
        self, provider: str, model_name: str
    ) -> ModelRecord | None:
        """Retrieve a model record by provider and model name.

        Args:
            provider: Provider name.
            model_name: Model identifier.

        Returns:
            ModelRecord or None if not found.
        """
        stmt = select(ModelAnonReqModel).where(
            and_(
                ModelAnonReqModel.provider == provider,
                ModelAnonReqModel.model_name == model_name,
            )
        )
        result = await self._db.execute(stmt)
        orm = result.scalars().unique().one_or_none()
        if orm is None:
            return None
        return _orm_to_model_record(orm)

    async def is_model_approved(self, provider: str, model_name: str) -> bool:
        """Check if a model is approved for use.

        Returns True only if the model exists and its current_stage
        is APPROVED or PRODUCTION. Unknown models return False
        (fail-secure: block what you don't know).

        Args:
            provider: Provider name.
            model_name: Model identifier.

        Returns:
            True if model exists and is approved, False otherwise.
        """
        record = await self.get_model_record_by_name(provider, model_name)
        if record is None:
            return False
        return record.current_stage in ("APPROVED", "PRODUCTION")

    async def list_models(
        self,
        risk_classification: ModelRiskClassification | None = None,
        provider: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ModelRecord]:
        """List model records with optional filtering.

        Args:
            risk_classification: Optional filter by risk classification.
            provider: Optional filter by provider name.
            skip: Number of records to skip (pagination).
            limit: Maximum records to return.

        Returns:
            List of ModelRecord objects.
        """
        stmt = select(ModelAnonReqModel)

        if risk_classification is not None:
            stmt = stmt.where(
                ModelAnonReqModel.risk_classification == risk_classification.value
            )
        if provider is not None:
            stmt = stmt.where(ModelAnonReqModel.provider == provider)

        stmt = stmt.offset(skip).limit(limit).order_by(ModelAnonReqModel.created_at.desc())
        result = await self._db.execute(stmt)
        orms = result.scalars().unique().all()
        return [_orm_to_model_record(o) for o in orms]

    async def update_model_review(
        self,
        model_id: str,
        validation_status: str,
        validation_date: datetime,
    ) -> ModelRecord:
        """Update model review fields.

        Sets validation status, date, and computes next review date
        based on the model's review cycle interval.

        Args:
            model_id: The model's unique identifier.
            validation_status: New validation status.
            validation_date: Date of validation.

        Returns:
            Updated ModelRecord.
        """
        stmt = select(ModelAnonReqModel).where(ModelAnonReqModel.model_id == model_id)
        result = await self._db.execute(stmt)
        orm = result.scalars().unique().one_or_none()
        if orm is None:
            raise ValueError(f"Model not found: {model_id}")

        now = datetime.now(timezone.utc)
        orm.validation_status = validation_status
        orm.validation_date = validation_date
        orm.last_review_date = now
        orm.next_review_date = (now + timedelta(days=orm.review_cycle_days)).replace(
            microsecond=0
        )
        orm.updated_at = now

        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_model_record(orm)

    @staticmethod
    def get_sr_11_7_alignment() -> dict[str, Any]:
        """Return SR 11-7 alignment documentation.

        Maps SR 11-7 principles to implementation details for
        compliance reporting and audit.
        """
        return {
            "model_risk_classification": {
                "principle": "Models classified by risk (LOW, MODERATE, HIGH)",
                "implementation": "ModelRiskClassification enum per SR 11-7 §3.2",
                "fields": ["risk_classification"],
            },
            "approval_gating": {
                "principle": "Unapproved models blocked from production use",
                "implementation": (
                    "ForwardingGuard checks is_model_approved() before dispatch; "
                    "only APPROVED/PRODUCTION stages permitted"
                ),
                "fields": ["current_stage", "approval_status"],
            },
            "review_cycle": {
                "principle": "Ongoing monitoring with periodic review cycles",
                "implementation": (
                    "Review cycle tracked via review_cycle_days, last_review_date, "
                    "next_review_date fields; update_model_review() computes next review"
                ),
                "fields": [
                    "review_cycle_days",
                    "last_review_date",
                    "next_review_date",
                ],
            },
            "documentation": {
                "principle": "Model documentation maintained and versioned",
                "implementation": (
                    "Documentation URL stored per model; version field tracks model version"
                ),
                "fields": ["documentation_url", "version"],
            },
            "validation": {
                "principle": "Models validated before production deployment",
                "implementation": (
                    "Validation status and date tracked per model; "
                    "PRODUCTION stage requires completed validation"
                ),
                "fields": ["validation_status", "validation_date"],
            },
        }


def _orm_to_model_record(orm: ModelAnonReqModel) -> ModelRecord:
    """Convert ORM model to Pydantic ModelRecord."""
    return ModelRecord(
        id=orm.model_id,
        provider=orm.provider,
        model_name=orm.model_name,
        risk_classification=ModelRiskClassification(orm.risk_classification),
        approval_status=orm.approval_status,
        current_stage=orm.current_stage,
        lifecycle_object_id=orm.lifecycle_object_id,
        version=orm.version,
        documentation_url=orm.documentation_url,
        validation_status=orm.validation_status,
        validation_date=_ensure_tz(orm.validation_date),
        review_cycle_days=orm.review_cycle_days,
        last_review_date=_ensure_tz(orm.last_review_date),
        next_review_date=_ensure_tz(orm.next_review_date),
        created_at=_ensure_tz(orm.created_at),
        updated_at=_ensure_tz(orm.updated_at),
    )


def _ensure_tz(dt: Any) -> Any:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
