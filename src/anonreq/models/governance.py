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


# ── SR 11-7 Model Risk Management ────────────────────────────────────────


class ModelRiskClassification(str, Enum):
    """SR 11-7 risk classification for models.

    Per SR 11-7, models are classified by their potential impact:
    - LOW: Limited impact, well-understood risks
    - MODERATE: Moderate impact, some complexity
    - HIGH: Significant impact, complex or novel
    """

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class ModelRecord(BaseModel):
    """SR 11-7 model inventory record.

    Tracks risk classification, approval status, review cycles,
    and lifecycle integration with Phase 14 LifecycleService.
    """

    id: str = ""
    provider: str
    model_name: str
    risk_classification: ModelRiskClassification
    approval_status: str = "pending"
    current_stage: str = "DRAFT"
    lifecycle_object_id: str = ""
    version: str = "1.0.0"
    documentation_url: str | None = None
    validation_status: str | None = None
    validation_date: datetime | None = None
    review_cycle_days: int = 365
    last_review_date: datetime | None = None
    next_review_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "ignore", "from_attributes": True}

    @field_validator("risk_classification", mode="before")
    @classmethod
    def coerce_risk_classification(cls, v: Any) -> ModelRiskClassification:
        if isinstance(v, ModelRiskClassification):
            return v
        if isinstance(v, str):
            return ModelRiskClassification(v.upper())
        raise ValueError(f"Invalid risk classification: {v}")


# ── DORA ICT Third-Party Provider Inventory ──────────────────────────────


class ProviderRecord(BaseModel):
    """Third-party provider record per DORA ICT requirements.

    Tracks provider status, DORA ICT critical designation,
    concentration risk, and lifecycle integration.
    """

    id: str = ""
    name: str
    provider_type: str
    status: str = "active"
    lifecycle_object_id: str = ""
    dora_ict_critical: bool = False
    concentration_risk: bool = False
    concentration_risk_justification: str | None = None
    concentration_risk_justification_date: datetime | None = None
    contract_end_date: datetime | None = None
    review_cycle_days: int = 365
    last_review_date: datetime | None = None
    next_review_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "ignore", "from_attributes": True}


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


class ModelAnonReqModel(SQLAlchemyBase):
    """SR 11-7 model inventory ORM model."""

    __tablename__ = "model_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(64), unique=True, nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model_name = Column(String(128), nullable=False)
    risk_classification = Column(String(32), nullable=False)
    approval_status = Column(String(32), nullable=False, default="pending")
    current_stage = Column(String(32), nullable=False, default="DRAFT")
    lifecycle_object_id = Column(String(64), nullable=False, default="")
    version = Column(String(32), nullable=False, default="1.0.0")
    documentation_url = Column(String(512), nullable=True)
    validation_status = Column(String(32), nullable=True)
    validation_date = Column(DateTime(timezone=True), nullable=True)
    review_cycle_days = Column(Integer, nullable=False, default=365)
    last_review_date = Column(DateTime(timezone=True), nullable=True)
    next_review_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ProviderAnonReqModel(SQLAlchemyBase):
    """DORA ICT third-party provider ORM model."""

    __tablename__ = "provider_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    provider_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    lifecycle_object_id = Column(String(64), nullable=False, default="")
    dora_ict_critical = Column(Boolean, nullable=False, default=False)
    concentration_risk = Column(Boolean, nullable=False, default=False)
    concentration_risk_justification = Column(Text, nullable=True)
    concentration_risk_justification_date = Column(DateTime(timezone=True), nullable=True)
    contract_end_date = Column(DateTime(timezone=True), nullable=True)
    review_cycle_days = Column(Integer, nullable=False, default=365)
    last_review_date = Column(DateTime(timezone=True), nullable=True)
    next_review_date = Column(DateTime(timezone=True), nullable=True)
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


def model_record_to_json(record: ModelRecord) -> str:
    return record.model_dump_json()


def json_to_model_record(raw: str) -> ModelRecord:
    return ModelRecord(**json.loads(raw))


def provider_record_to_json(record: ProviderRecord) -> str:
    return record.model_dump_json()


def json_to_provider_record(raw: str) -> ProviderRecord:
    return ProviderRecord(**json.loads(raw))
