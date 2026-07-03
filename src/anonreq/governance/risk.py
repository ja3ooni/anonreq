"""Risk assessment framework with 6 core dimensions.

Provides async functions for creating, updating, and querying risk
assessments, including dimension scoring, overall score computation,
and reassessment flagging.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.governance import (
    RISK_DIMENSIONS_CORE,
    RiskAssessment,
    RiskAssessmentModel,
    RiskDimensionScore,
    dimensions_to_json,
    json_to_dimensions,
)


def compute_dimension_score(severity: int, likelihood: int) -> float:
    """Compute a single dimension's overall score.

    Score = severity * likelihood / 25, normalized to 0-1 range.

    Args:
        severity: Severity rating (1-5).
        likelihood: Likelihood rating (1-5).

    Returns:
        Float between 0.04 and 1.0.
    """
    return round((severity * likelihood) / 25.0, 4)


def compute_overall_risk_score(
    dimensions: list[RiskDimensionScore],
) -> float:
    """Compute weighted average across all dimension scores.

    All dimensions are equally weighted.

    Args:
        dimensions: List of RiskDimensionScore objects.

    Returns:
        Float between 0.0 and 1.0.
    """
    if not dimensions:
        return 0.0
    total = sum(d.overall_score for d in dimensions)
    return round(total / len(dimensions), 4)


async def create_risk_assessment(
    db: AsyncSession,
    tenant_id: str,
    governance_record_id: int,
    dimensions: list[RiskDimensionScore],
    extensions: list[RiskDimensionScore] | None = None,
) -> RiskAssessment:
    """Create a new risk assessment for a governance record.

    Validates that core dimensions are present, computes overall score.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        governance_record_id: FK to governance_record.
        dimensions: List of core+extension dimension scores.
        extensions: Optional extra dimensions beyond the 6 core.

    Returns:
        Created RiskAssessment.

    Raises:
        ValueError: If core dimensions are missing.
    """
    _validate_core_dimensions(dimensions, extensions)

    all_dims = list(dimensions)
    if extensions:
        all_dims.extend(extensions)

    for d in all_dims:
        d.overall_score = compute_dimension_score(d.severity, d.likelihood)

    overall = compute_overall_risk_score(all_dims)
    now = datetime.now(timezone.utc)

    assessment = RiskAssessmentModel(
        tenant_id=tenant_id,
        governance_record_id=governance_record_id,
        dimensions=dimensions_to_json(dimensions),
        extensions=dimensions_to_json(extensions) if extensions else None,
        overall_risk_score=overall,
        reassessment_required=False,
        created_at=now,
        updated_at=now,
    )
    db.add(assessment)
    await db.flush()
    await db.refresh(assessment)

    return _model_to_assessment(assessment)


async def get_risk_assessment(
    db: AsyncSession,
    tenant_id: str,
) -> RiskAssessment | None:
    """Fetch the latest risk assessment for a tenant.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.

    Returns:
        RiskAssessment or None.
    """
    stmt = (
        select(RiskAssessmentModel)
        .where(RiskAssessmentModel.tenant_id == tenant_id)
        .order_by(RiskAssessmentModel.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    model = result.scalars().one_or_none()
    if model is None:
        return None
    return _model_to_assessment(model)


async def update_risk_assessment(
    db: AsyncSession,
    tenant_id: str,
    dimensions: list[RiskDimensionScore],
    extensions: list[RiskDimensionScore] | None = None,
) -> RiskAssessment:
    """Update dimensions and recompute score on the latest assessment.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        dimensions: Updated core dimensions.
        extensions: Updated extension dimensions.

    Returns:
        Updated RiskAssessment.

    Raises:
        ValueError: If no assessment exists for tenant.
    """
    _validate_core_dimensions(dimensions, extensions)

    stmt = (
        select(RiskAssessmentModel)
        .where(RiskAssessmentModel.tenant_id == tenant_id)
        .order_by(RiskAssessmentModel.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    model = result.scalars().one_or_none()
    if model is None:
        raise ValueError(f"No risk assessment for tenant: {tenant_id}")

    all_dims = list(dimensions)
    if extensions:
        all_dims.extend(extensions)

    for d in all_dims:
        d.overall_score = compute_dimension_score(d.severity, d.likelihood)

    model.dimensions = dimensions_to_json(dimensions)
    model.extensions = dimensions_to_json(extensions) if extensions else None
    model.overall_risk_score = compute_overall_risk_score(all_dims)
    model.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(model)

    return _model_to_assessment(model)


async def flag_reassessment(
    db: AsyncSession,
    tenant_id: str,
    reason: str,
) -> RiskAssessment:
    """Set the reassessment_required flag on the latest assessment.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        reason: Human-readable reason for the reassessment.

    Returns:
        Updated RiskAssessment.

    Raises:
        ValueError: If no assessment exists for tenant.
    """
    stmt = (
        select(RiskAssessmentModel)
        .where(RiskAssessmentModel.tenant_id == tenant_id)
        .order_by(RiskAssessmentModel.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    model = result.scalars().one_or_none()
    if model is None:
        raise ValueError(f"No risk assessment for tenant: {tenant_id}")

    model.reassessment_required = True
    model.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(model)

    return _model_to_assessment(model)


async def check_config_triggers_reassessment(
    db: AsyncSession,
    tenant_id: str,
    changed_fields: list[str],
) -> bool:
    """Check if config changes affect entity types and flag reassessment.

    Entity-type-related fields include: entity_types, detection,
    recognizer, analyzer_config, presidio, custom_recognizers.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant identifier.
        changed_fields: List of config field names that changed.

    Returns:
        True if reassessment was flagged, False otherwise.
    """
    trigger_fields = {
        "entity_types",
        "detection",
        "recognizer",
        "analyzer_config",
        "presidio",
        "custom_recognizers",
        "pii_entities",
        "classification_rules",
    }
    affected = trigger_fields & set(changed_fields)
    if not affected:
        return False

    await flag_reassessment(
        db,
        tenant_id,
        f"Config change triggered reassessment (fields: {', '.join(sorted(affected))})",
    )
    return True


def _validate_core_dimensions(
    dimensions: list[RiskDimensionScore],
    extensions: list[RiskDimensionScore] | None = None,
) -> None:
    """Validate that all core risk dimensions are present.

    Args:
        dimensions: List of dimension scores to validate.

    Raises:
        ValueError: If a core dimension is missing.
    """
    found = {d.dimension for d in dimensions}
    missing = [d for d in RISK_DIMENSIONS_CORE if d not in found]
    if missing:
        raise ValueError(f"Missing core dimensions: {', '.join(missing)}")


def _model_to_assessment(model: RiskAssessmentModel) -> RiskAssessment:
    """Convert ORM model to Pydantic RiskAssessment."""
    dims = json_to_dimensions(model.dimensions)
    exts = json_to_dimensions(model.extensions) if model.extensions else None

    return RiskAssessment(
        id=model.id,
        tenant_id=model.tenant_id,
        governance_record_id=model.governance_record_id,
        dimensions=dims,
        extensions=exts,
        overall_risk_score=model.overall_risk_score,
        reassessment_required=bool(model.reassessment_required),
        created_at=_ensure_tz(model.created_at),
        updated_at=_ensure_tz(model.updated_at),
    )


def _ensure_tz(dt: Any) -> Any:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
