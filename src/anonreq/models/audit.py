"""Audit event model with SHA-384 hash chaining.

Provides:
- ``AuditEvent``: Dataclass representing a single audit event.
- ``AuditEventModel``: SQLAlchemy ORM model for PostgreSQL storage.
- ``DailyAnchor``: Dataclass representing a daily chain anchor.
- ``compute_event_hash``: Compute SHA-384 hash over canonical event fields.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for AnonReq models."""


class AuditEventModel(Base):
    """SQLAlchemy ORM model for the audit_event table.

    Maps to the ``audit_event`` table in PostgreSQL. Used by Alembic
    for migrations and by AuditChainService for DB operations.
    """

    __tablename__ = "audit_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False)
    prev_hash = Column(String(96), nullable=True)
    hash = Column(String(96), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    tenant_id = Column(String(64), nullable=False)
    request_id = Column(String(64), nullable=True)
    policy_id = Column(String(64), nullable=True)
    decision = Column(String(32), nullable=True)
    provider = Column(String(64), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    event_type = Column(String(64), nullable=False)
    operator_id = Column(String(64), nullable=True)
    change_type = Column(String(64), nullable=True)
    prev_value_hash = Column(String(96), nullable=True)
    new_value_hash = Column(String(96), nullable=True)
    metadata_json = Column(Text, nullable=True)
    retention_days = Column(Integer, nullable=False, server_default="2557")


@dataclass
class AuditEvent:
    """Immutable audit event with hash chain support.

    Each event stores the hash of the previous event in the chain,
    forming a tamper-evident linked list. The ``hash`` field is the
    SHA-384 digest of all other fields serialized as canonical JSON.

    Attributes:
        event_id: Unique event identifier.
        prev_hash: SHA-384 hex digest of previous event (None if first).
        hash: SHA-384 hex digest of this event's fields.
        timestamp: Event timestamp (timezone-aware).
        tenant_id: Tenant identifier.
        request_id: Optional request correlation ID.
        policy_id: Optional policy identifier that triggered the event.
        decision: Optional policy decision.
        provider: Optional LLM provider name.
        latency_ms: Optional request latency in milliseconds.
        event_type: Event type (e.g. config_change, policy_decision).
        operator_id: Optional operator who performed the action.
        change_type: Optional type of configuration change.
        prev_value_hash: Optional SHA-384 of previous config value.
        new_value_hash: Optional SHA-384 of new config value.
        metadata_json: Optional arbitrary JSON metadata.
        retention_days: Retention period in days (default 2557 = 7 years).
    """

    event_id: str
    prev_hash: str | None
    hash: str
    timestamp: datetime
    tenant_id: str
    request_id: str | None
    policy_id: str | None
    decision: str | None
    provider: str | None
    latency_ms: int | None
    event_type: str
    operator_id: str | None
    change_type: str | None
    prev_value_hash: str | None
    new_value_hash: str | None
    metadata_json: str | None
    retention_days: int = 2557


def compute_event_hash(event: AuditEvent) -> str:
    """Compute SHA-384 hash over canonical JSON of event fields.

    Hashes all fields *except* ``hash`` itself (to avoid circularity)
    and ``retention_days`` (operational, not part of the audit record).

    Uses ``sort_keys=True`` with compact separators for determinism.

    Args:
        event: The AuditEvent to hash.

    Returns:
        SHA-384 hex digest string (96 characters).
    """
    data = {
        "event_id": event.event_id,
        "prev_hash": event.prev_hash,
        "timestamp": event.timestamp.isoformat(),
        "tenant_id": event.tenant_id,
        "request_id": event.request_id,
        "policy_id": event.policy_id,
        "decision": event.decision,
        "provider": event.provider,
        "latency_ms": event.latency_ms,
        "event_type": event.event_type,
        "operator_id": event.operator_id,
        "change_type": event.change_type,
        "prev_value_hash": event.prev_value_hash,
        "new_value_hash": event.new_value_hash,
        "metadata_json": event.metadata_json,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha384(canonical.encode()).hexdigest()


@dataclass
class DailyAnchor:
    """Daily chain anchor for tamper-evident audit trail.

    Computed at end of each day from all events on that date.
    The daily_root_hash is the SHA-384 of concatenated event hashes.
    The signature is HMAC-SHA384 of the daily_root_hash.

    Attributes:
        anchor_date: The date this anchor covers.
        daily_root_hash: SHA-384 of concatenated event hashes.
        signature: HMAC-SHA384 signature of the root hash.
        event_count: Number of events in this day.
        created_at: When the anchor was created.
        verified_at: When the anchor was last verified.
    """

    anchor_date: date
    daily_root_hash: str
    signature: str
    event_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: datetime | None = None
