"""Governance, review cycle, and risk assessment models.

Provides:
- ``GovernanceOfficerRole`` enum
- ``GovernanceOfficer``, ``ReviewCycle``, ``GovernanceRecord`` Pydantic models
- ``RiskDimensionScore``, ``RiskAssessment`` Pydantic models
- ``ReviewCycleModel``, ``GovernanceRecordModel``, ``RiskAssessmentModel`` ORM models
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from anonreq.models.audit import Base as SQLAlchemyBase


class GovernanceOfficerRole(str, Enum):
    GOVERNANCE = "governance"
    RISK = "risk"
    COMPLIANCE = "compliance"
    SECURITY = "security"


class GovernanceOfficer(BaseModel):
    role: GovernanceOfficerRole
    name: str
    email: str

    model_config = {"extra": "ignore"}


class GovernanceOfficerUpdate(BaseModel):
    officers: list[GovernanceOfficer]

    model_config = {"extra": "ignore"}


class ReviewCycle(BaseModel):
    id: int
    tenant_id: str
    interval_days: int = 90
    last_review_date: datetime | None = None
    next_review_date: datetime | None = None
    status: str = "active"

    model_config = {"extra": "ignore", "from_attributes": True}


class ChangeEntry(BaseModel):
    version: int
    changed_at: datetime
    changed_by: str
    description: str
    changes: dict[str, str] = {}

    model_config = {"extra": "ignore"}


class GovernanceRecord(BaseModel):
    id: int
    tenant_id: str
    officers: list[GovernanceOfficer]
    review_cycle: ReviewCycle
    created_at: datetime
    updated_at: datetime
    status: str = "active"
    version: int = 1
    change_history: list[ChangeEntry] = []

    model_config = {"extra": "ignore", "from_attributes": True}


class RiskDimensionScore(BaseModel):
    dimension: str
    severity: int
    likelihood: int
    overall_score: float
    treatment_plan: str | None = None

    model_config = {"extra": "ignore"}

    @field_validator("severity", "likelihood")
    @classmethod
    def validate_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Must be between 1 and 5")
        return v


class RiskAssessment(BaseModel):
    id: int
    tenant_id: str
    governance_record_id: int
    dimensions: list[RiskDimensionScore]
    extensions: list[RiskDimensionScore] | None = None
    overall_risk_score: float
    reassessment_required: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"extra": "ignore", "from_attributes": True}


RISK_DIMENSIONS_CORE: list[str] = [
    "privacy",
    "security",
    "bias",
    "explainability",
    "fairness",
    "safety",
]


# ── SQLAlchemy ORM models ────────────────────────────────────────────────


class ReviewCycleModel(SQLAlchemyBase):
    __tablename__ = "review_cycle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    interval_days = Column(Integer, nullable=False, default=90)
    last_review_date = Column(DateTime(timezone=True), nullable=True)
    next_review_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="active")


class GovernanceRecordModel(SQLAlchemyBase):
    __tablename__ = "governance_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), unique=True, nullable=False, index=True)
    officers = Column(Text, nullable=False)
    review_cycle_id = Column(Integer, ForeignKey("review_cycle.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    change_history = Column(Text, nullable=True)

    review_cycle = relationship("ReviewCycleModel", lazy="joined")


class RiskAssessmentModel(SQLAlchemyBase):
    __tablename__ = "risk_assessment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    governance_record_id = Column(
        Integer, ForeignKey("governance_record.id"), nullable=False
    )
    dimensions = Column(Text, nullable=False)
    extensions = Column(Text, nullable=True)
    overall_risk_score = Column(Float, nullable=False)
    reassessment_required = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


# ── Serialization helpers ────────────────────────────────────────────────


def officers_to_json(officers: list[GovernanceOfficer]) -> str:
    return json.dumps([o.model_dump() for o in officers])


def dimensions_to_json(dimensions: list[RiskDimensionScore]) -> str:
    return json.dumps([d.model_dump() for d in dimensions])


def json_to_officers(raw: str) -> list[GovernanceOfficer]:
    return [GovernanceOfficer(**o) for o in json.loads(raw)]


def json_to_dimensions(raw: str) -> list[RiskDimensionScore]:
    return [RiskDimensionScore(**d) for d in json.loads(raw)]


def change_history_to_json(history: list[ChangeEntry]) -> str:
    return json.dumps([e.model_dump() for e in history])


def json_to_change_history(raw: str | None) -> list[ChangeEntry]:
    if not raw:
        return []
    return [ChangeEntry(**e) for e in json.loads(raw)]
