"""Regulator-safe projections of audit events. Never include raw PII."""

from __future__ import annotations

import json
from typing import Any

_EXPORT_METADATA_KEYS = (
    "entity_types",
    "entity_counts",
    "token_count",
    "locale",
    "model",
    "compliance_preset",
)


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
