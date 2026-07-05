"""Data models for data lineage, Legal Hold, and supplier governance.

Provides:
- ``LineageRecord``: Immutable per-session lineage record (D-009, D-010)
- ``LegalHoldRecord``: Legal Hold with tenant-level and record-level tagging (D-018)
- ``SupplierGovernanceRecord``: Third-party AI supplier governance (D-012)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LineageRecord(BaseModel):
    """Immutable per-session data lineage record (D-009).

    Records full provenance for a single request: session metadata,
    provider, model, entities detected, and policies applied.

    Per D-010: Stored in PostgreSQL (queryable) + MinIO archive (JSONL).
    Per D-011: No API to modify or delete lineage records.
    """

    id: str = ""
    session_id: str
    tenant_id: str
    provider: str | None = None
    model: str | None = None
    entity_types: list[str] = []
    entity_count: int = 0
    policies_applied: list[str] = []
    classification_action: str | None = None
    processing_time_ms: int = 0
    request_timestamp: datetime | None = None
    response_timestamp: datetime | None = None
    cache_hit: bool = False
    success: bool = True
    error_type: str | None = None

    model_config = {"extra": "ignore", "from_attributes": True}


class LegalHoldRecord(BaseModel):
    """Legal Hold with tenant-level and record-level tagging (D-018).

    Per D-019: Hold suspension blocks deletion across all storage tiers.
    Per D-020: Release of hold triggers normal retention policy.
    """

    id: str = ""
    tenant_id: str
    scope: Literal["tenant", "record"] = "tenant"
    record_id: str | None = None
    reason: str = ""
    activated_by: str = ""
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    released_at: datetime | None = None
    released_by: str | None = None

    model_config = {"extra": "ignore", "from_attributes": True}


class SupplierGovernanceRecord(BaseModel):
    """Third-party AI supplier governance record (D-012).

    Tracks provider inventory with contract/risk/review status.
    Per D-013: Provider review cycle defaults to 365 days.
    Per D-014: Uses Phase 14 lifecycle stages.
    Per D-015: Risk re-evaluation triggers configurable.
    """

    id: str = ""
    name: str
    provider_type: str = ""
    contract_status: str = "active"
    risk_status: str = "low"
    review_cycle_days: int = 365
    last_review_date: datetime | None = None
    next_review_date: datetime | None = None
    lifecycle_object_id: str = ""
    risk_re_evaluation_triggers: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "ignore", "from_attributes": True}
