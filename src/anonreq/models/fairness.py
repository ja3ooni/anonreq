"""Fairness data models for PII detection bias assessment.

Per D-001 through D-005:
- FairnessDataset: metadata for a bias evaluation dataset
- DemographicResult: recall result for one demographic group
- FairnessResult: evaluation result for one entity type
- FairnessEvaluation: aggregate evaluation across entity types

Per D-008:
- IncidentSeverity: Critical/High/Medium/Low incident severity levels
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@dataclass
class FairnessDataset:
    """Metadata for a fairness evaluation dataset stored in MinIO.

    The dataset content itself (JSONL) is stored in MinIO addressed by
    SHA-256 content hash. This model holds only the metadata registry.
    """

    id: str
    sha256: str
    owner: str
    approved_by: str
    approval_date: datetime
    framework: str
    version: str
    locale: str
    group_sizes: dict[str, int] = field(default_factory=dict)
    entity_type: str = "PERSON"
    total_examples: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=None))


@dataclass
class DemographicResult:
    """Recall result for a single demographic group."""

    group: str
    total: int
    detected: int
    recall: float = 0.0

    def __post_init__(self) -> None:
        if self.total > 0 and self.recall == 0.0:
            object.__setattr__(self, "recall", self.detected / self.total)


@dataclass
class FairnessResult:
    """Evaluation result for one entity type across demographic groups."""

    entity_type: str
    overall_recall: float
    demographic_results: list[DemographicResult] = field(default_factory=list)
    max_disparity: float = 0.0
    threshold: float = 0.05
    passed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "passed", self.max_disparity <= self.threshold)


@dataclass
class FairnessEvaluation:
    """Complete fairness evaluation across all entity types.

    Emitted as an audit event on completion.
    """

    id: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(tz=None))
    version: str = "1.0"
    results: list[FairnessResult] = field(default_factory=list)
    overall_passed: bool = True
    dataset_id: str = ""
    git_sha: str | None = None

    def __post_init__(self) -> None:
        if self.results:
            object.__setattr__(self, "overall_passed", all(r.passed for r in self.results))


class FairnessDatasetModel(Base):
    """SQLAlchemy ORM model for fairness dataset metadata registry."""

    __tablename__ = "fairness_dataset"

    id = Column(String(64), primary_key=True)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    owner = Column(String(128), nullable=False)
    approved_by = Column(String(128), nullable=False)
    approval_date = Column(DateTime, nullable=False)
    framework = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    locale = Column(String(16), nullable=False)
    group_sizes = Column(Text, nullable=True)
    entity_type = Column(String(32), nullable=False, default="PERSON")
    total_examples = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)


class ProductionMetricModel(Base):
    """Per-session detection quality metric for monitoring drift."""

    __tablename__ = "fairness_production_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False)
    demographic_group = Column(String(32), nullable=False)
    detected = Column(Boolean, nullable=False)
    recorded_at = Column(DateTime, nullable=False)


class IncidentSeverity(IntEnum):
    """Severity levels for fairness incidents (D-008).

    Higher ordinal = more severe.
    """

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


INCIDENT_RESPONSE_TIMES: dict[str, str] = {
    "CRITICAL": "immediate",
    "HIGH": "24h",
    "MEDIUM": "72h",
    "LOW": "next_review",
}


@dataclass
class IncidentRecord:
    """Record of a fairness incident created by the drift monitor."""

    id: str
    severity: IncidentSeverity
    incident_type: str
    entity_type: str
    drift_amount: float
    baseline_recall: float
    production_recall: float
    detected_at: datetime = field(default_factory=lambda: datetime.now(tz=None))
    acknowledged: bool = False
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def dataset_model_to_dataclass(row: Any) -> FairnessDataset:
    """Convert a SQLAlchemy FairnessDatasetModel row to a FairnessDataset dataclass."""
    return FairnessDataset(
        id=row.id,
        sha256=row.sha256,
        owner=row.owner,
        approved_by=row.approved_by,
        approval_date=row.approval_date,
        framework=row.framework,
        version=row.version,
        locale=row.locale,
        group_sizes=json.loads(row.group_sizes) if row.group_sizes else {},
        entity_type=row.entity_type,
        total_examples=row.total_examples,
        created_at=row.created_at,
    )
