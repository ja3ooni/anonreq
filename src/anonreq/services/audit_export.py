"""Regulator-safe projections of audit events. Never include raw PII."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

_EXPORT_METADATA_KEYS = (
    "entity_types",
    "entity_counts",
    "token_count",
    "locale",
    "model",
    "compliance_preset",
)

ANONYMIZATION_EVENT_FIELDS: tuple[str, ...] = (
    "request_id",
    "timestamp",
    "tenant_id",
    "model",
    "locale",
    "decision",
    "token_count",
    "entity_types",
)

# Page size for streaming anonymization CSV exports. Kept well under the
# historical 10_000-row cap so a generator walks every matching row.
ANONYMIZATION_EXPORT_PAGE_SIZE = 1000


def safe_anonymization_row(event: Any) -> dict[str, Any]:
    """Project an audit event into a regulator-safe row (no raw values)."""
    metadata: dict[str, Any] = {}
    if event.metadata_json:
        try:
            parsed = json.loads(event.metadata_json)
            if isinstance(parsed, dict):
                metadata = {k: parsed[k] for k in _EXPORT_METADATA_KEYS if k in parsed}
        except json.JSONDecodeError:
            metadata = {}
    entity_types = metadata.get("entity_types") or list(metadata.get("entity_counts", {}))
    return {
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "request_id": event.request_id,
        "tenant_id": event.tenant_id,
        "operator_id": event.operator_id,
        "model": metadata.get("model") or event.provider,
        "locale": metadata.get("locale"),
        "entity_types": (
            ",".join(str(t) for t in entity_types)
            if isinstance(entity_types, list)
            else str(entity_types)
        ),
        "token_count": metadata.get("token_count"),
        "decision": event.decision,
        "compliance_preset": metadata.get("compliance_preset"),
    }


def iso_utc(value: datetime | None) -> str | None:
    """Format a timestamp as ISO-8601 UTC with a Z suffix."""
    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def _metadata(event: Any) -> dict[str, Any]:
    if not event.metadata_json:
        return {}
    try:
        parsed = json.loads(event.metadata_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def entity_type_counts(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Build ``[{type, count}]`` from regulator-safe metadata.

    ``entity_counts`` wins when present. Types listed without a count
    are reported as 1. Raw values are never read.
    """
    merged: dict[str, int] = {}
    counts = metadata.get("entity_counts")
    if isinstance(counts, dict):
        for key, value in counts.items():
            try:
                merged[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
    listed = metadata.get("entity_types")
    if isinstance(listed, list):
        for item in listed:
            if isinstance(item, str) and item not in merged:
                merged[item] = 1
    return [{"type": key, "count": merged[key]} for key in sorted(merged)]


def anonymization_event_record(event: Any) -> dict[str, Any]:
    """One anonymization event row. Metadata only — never raw PII."""
    metadata = _metadata(event)
    model = metadata.get("model") or event.provider
    token_count = metadata.get("token_count")
    if token_count is not None:
        try:
            token_count = int(token_count)
        except (TypeError, ValueError):
            token_count = None
    return {
        "request_id": event.request_id,
        "timestamp": iso_utc(event.timestamp),
        "tenant_id": event.tenant_id,
        "model": model,
        "locale": metadata.get("locale"),
        "decision": event.decision,
        "token_count": token_count,
        "entity_types": entity_type_counts(metadata),
    }


async def iter_filtered_events(service: Any, **filters: Any) -> Any:
    """Yield every matching audit event, paging past the old 10k cap."""
    offset = 0
    page = ANONYMIZATION_EXPORT_PAGE_SIZE
    while True:
        batch = await service.get_events(limit=page, offset=offset, **filters)
        if not batch:
            break
        for event in batch:
            yield event
        if len(batch) < page:
            break
        offset += len(batch)


def anonymization_event_csv_row(record: dict[str, Any]) -> dict[str, Any]:
    """CSV projection. ``entity_types`` is a JSON array in one column."""
    row: dict[str, Any] = {}
    for key in ANONYMIZATION_EVENT_FIELDS:
        value = record.get(key)
        if key == "entity_types":
            row[key] = json.dumps(value or [], separators=(",", ":"), ensure_ascii=False)
        elif value is None:
            row[key] = ""
        else:
            row[key] = value
    return row
