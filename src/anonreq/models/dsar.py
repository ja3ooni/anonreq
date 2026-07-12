"""Data Subject Access Request (DSAR) data models.

Per D-021 through D-025:
- DsarRequestType: ERASURE, RESTRICTION, RECTIFICATION, PORTABILITY, ACCESS
- SubjectStatus: ACTIVE, DELETED, PROCESSING_RESTRICTED, LEGAL_HOLD
- DsarRequest: Full request with status tracking and verification
- DsarResult: Outcome of a fulfilled DSAR request
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DsarRequestType(StrEnum):
    """Type of Data Subject Access Request.

    Per D-021: Standard DSAR request types covering all data subject
    rights under GDPR/CCPA.
    """

    ERASURE = "ERASURE"
    RESTRICTION = "RESTRICTION"
    RECTIFICATION = "RECTIFICATION"
    PORTABILITY = "PORTABILITY"
    ACCESS = "ACCESS"


class SubjectStatus(StrEnum):
    """Status of a data subject after DSAR fulfillment.

    Per D-025:
    - ``ACTIVE``: Subject has no outstanding DSAR actions
    - ``DELETED``: Subject data has been erased per D-022
    - ``PROCESSING_RESTRICTED``: Subject requests are blocked per D-023
    - ``LEGAL_HOLD``: Subject under Legal Hold, erasure blocked per D-024
    """

    ACTIVE = "active"
    DELETED = "deleted"
    PROCESSING_RESTRICTED = "processing_restricted"
    LEGAL_HOLD = "legal_hold"


class DsarRequest(BaseModel):
    """A Data Subject Access Request.

    Tracks the full lifecycle: submitted → verified → fulfilled.
    """

    id: str = ""
    tenant_id: str
    subject_id: str
    request_type: DsarRequestType
    status: str = "pending_verification"
    verified_by: str | None = None
    fulfilled_by: str | None = None
    verification_details: dict | None = None
    result: SubjectStatus | None = None
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    fulfilled_at: datetime | None = None
    notes: str | None = None

    model_config = {"extra": "ignore", "from_attributes": True}


class DsarResult(BaseModel):
    """Result of a fulfilled DSAR request.

    Contains the final subject_status and fulfillment metadata.
    """

    request_id: str
    subject_status: SubjectStatus
    summary: str = ""
    fulfilled_at: datetime | None = None

    model_config = {"extra": "ignore"}
