"""Pydantic models for eDiscovery exports.

Defines request/result models used by the eDiscovery export engine.
Supports three export formats: JSONL, PDF summary, and EDRM XML.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ExportFormat(StrEnum):
    """Supported eDiscovery export formats."""

    JSONL = "jsonl"
    PDF = "pdf"
    EDRM_XML = "edrm_xml"


class eDiscoveryExportRequest(BaseModel):  # noqa: N801
    """Request parameters for eDiscovery export.

    Attributes:
        tenant_id: Required tenant identifier.
        date_from: Optional start of date range (inclusive).
        date_to: Optional end of date range (inclusive).
        entity_types: Optional list of entity type filters.
        case_reference: Optional case/matter reference.
        format: Export format (jsonl, pdf, edrm_xml).
        skip: Number of records to skip (pagination).
        limit: Maximum records to return (pagination).
    """

    tenant_id: str
    date_from: datetime | None = None
    date_to: datetime | None = None
    entity_types: list[str] | None = None
    case_reference: str | None = None
    format: ExportFormat = ExportFormat.JSONL
    skip: int = 0
    limit: int = 100


class eDiscoveryExportResult(BaseModel):  # noqa: N801
    """Result of an eDiscovery export operation.

    Attributes:
        format: The export format used.
        content: The exported content (string for JSONL/XML, base64 for PDF).
        content_type: MIME type of the export.
        file_extension: File extension for the export.
        filename: Generated filename for the export.
        record_count: Number of records exported.
        export_timestamp: When the export was generated.
    """

    format: ExportFormat
    content: str
    content_type: str
    file_extension: str
    filename: str
    record_count: int
    export_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )


class EDRMMetadata(BaseModel):
    """EDRM XML case/request metadata.

    Used to populate the header of EDRM XML export files.
    """

    case_id: str = ""
    case_name: str = ""
    matter: str = ""
    customer: str = ""
    request_id: str = ""
    request_name: str = ""
    request_type: str = "PRODUCTION"
    notes: str = ""
