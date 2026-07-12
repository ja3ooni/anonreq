"""Pydantic response models for Trust Center public endpoints."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class FrameworkInfo(BaseModel):
    id: str
    name: str
    description: str
    jurisdictions: list[str]


class TrustStatus(BaseModel):
    slo_count: int
    compliant_count: int
    overall_percentage: float
    last_breach: datetime | None
    period: str


class TrustCompliance(BaseModel):
    frameworks: list[FrameworkInfo]


class TrustMetrics(BaseModel):
    total_requests: float
    total_entities: float
    fail_secure_count: float
    latency_p50_ms: float
    latency_p99_ms: float
    uptime_days: float


class TrustSecurity(BaseModel):
    display_name: str
    contact_email: str
    logo_url: str
    feature_summary: dict[str, bool]
    security_contact: str
    certifications: list[dict[str, str]]
