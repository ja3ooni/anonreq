"""Regulator-safe projections of audit events. Never include raw PII."""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
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

# Presidio-style labels: letters and underscores, no digits, so an IBAN or
# other numeric identifier cannot pass as an entity type.
_ENTITY_TYPE_RE = re.compile(r"^[A-Z][A-Z_]{1,63}$")
# Operator names: one Unicode letter, then letters, digits, spaces, and
# common separators (space, period, apostrophe, underscore, hyphen). The
# str pattern is Unicode-aware. 64 characters matches the audit column.
_OPERATOR_MAX_LEN = 64
_OPERATOR_ID_RE = re.compile("^[^\\W\\d_](?:[^\\W\\d_]|[\\d ._'\\-\u2019]){0,63}\\Z")
_OPERATOR_MAX_DIGITS = 6
# Model ids (gpt-4o, llama3.3:70b, claude-sonnet-4). No spaces or addresses.
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_IBAN_RE = re.compile(r"^[A-Za-z]{2}\d{2}[A-Za-z0-9]{11,30}$")
# ASCII formula leads, LF, the DDE pipe, and full-width forms of = + - @.
_FORMULA_LEAD = frozenset("=+-@\t\r\n|\uff1d\uff0b\uff0d\uff20")

ANONYMIZATION_CSV_FIELDS: tuple[str, ...] = (
    "timestamp",
    "request_id",
    "tenant_id",
    "operator_id",
    "model",
    "locale",
    "entity_types",
    "token_count",
    "decision",
    "compliance_preset",
)

_UTF8_BOM = b"\xef\xbb\xbf"


def _valid_entity_type_names(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str) and _ENTITY_TYPE_RE.fullmatch(item):
            names.append(item)
    return names


def _entity_types_cell(metadata: Mapping[str, Any]) -> str:
    names = _valid_entity_type_names(metadata.get("entity_types"))
    if not names:
        counts = metadata.get("entity_counts")
        if isinstance(counts, dict):
            names = _valid_entity_type_names(list(counts.keys()))
    return ",".join(names)


def _is_iban_like(text: str) -> bool:
    if _IBAN_RE.fullmatch(text):
        return True
    compact = re.sub(r"[\s-]", "", text)
    return bool(compact) and compact != text and _IBAN_RE.fullmatch(compact) is not None


def _valid_operator_id(value: object) -> str | None:
    """Keep a Unicode personal name or short id. Drop formulas, emails, IBANs."""
    if not isinstance(value, str):
        return None
    raw = unicodedata.normalize("NFC", value)
    if not raw.strip():
        return None
    # Reject formula leads before stripping, so a leading tab is not dropped
    # and then accepted as a name.
    probe = raw.lstrip(" ")
    if raw[0] in _FORMULA_LEAD or (probe and probe[0] in _FORMULA_LEAD):
        return None
    text = raw.strip()
    if len(text) > _OPERATOR_MAX_LEN:
        return None
    if "@" in text:
        return None
    if _is_iban_like(text):
        return None
    if sum(char.isdigit() for char in text) > _OPERATOR_MAX_DIGITS:
        return None
    if _OPERATOR_ID_RE.fullmatch(text) is None:
        return None
    return text


def _valid_model_name(value: object) -> str | None:
    if not isinstance(value, str) or not _MODEL_RE.fullmatch(value):
        return None
    if _IBAN_RE.fullmatch(value):
        return None
    letters = sum(char.isalpha() for char in value)
    digits = sum(char.isdigit() for char in value)
    if letters == 0:
        return None
    # Account-shaped tokens (long digit runs, almost no letters, no version
    # separator) are not model ids. Dated model names keep their separators.
    if digits >= 8 and letters <= 4 and not any(sep in value for sep in "-.:/"):
        return None
    return value


def _export_model(metadata: Mapping[str, Any], provider: object) -> str | None:
    model = _valid_model_name(metadata.get("model"))
    if model is not None:
        return model
    return _valid_model_name(provider)


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _token_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def sanitize_request_id(value: object) -> str | None:
    """Drop CR/LF so a request id cannot break a CSV row or inject another."""
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\r", "").replace("\n", "")
    return cleaned or None


def escape_csv_formula(value: object) -> str:
    """Prefix a leading spreadsheet formula so the cell is stored as text.

    Triggers are ``=``, ``+``, ``-``, ``@``, ``|``, tab, CR, LF, and the
    full-width forms U+FF1D, U+FF0B, U+FF0D, and U+FF20, including after
    leading spaces.
    """
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return ""
    probe = text.lstrip(" ")
    if text[0] in _FORMULA_LEAD or (probe and probe[0] in _FORMULA_LEAD):
        return "'" + text
    return text


def safe_anonymization_row(event: Any) -> dict[str, Any]:
    """Project an audit event into a regulator-safe row (no raw values).

    ``model`` and ``entity_types`` must match an identifier pattern.
    ``operator_id`` may be a Unicode name: letters, digits, spaces, and
    common separators, at most 64 characters. Formula prefixes, emails,
    and IBAN-like values are dropped.
    """
    metadata: dict[str, Any] = {}
    if event.metadata_json:
        try:
            parsed = json.loads(event.metadata_json)
            if isinstance(parsed, dict):
                metadata = {key: parsed[key] for key in _EXPORT_METADATA_KEYS if key in parsed}
        except json.JSONDecodeError:
            metadata = {}
    return {
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "request_id": sanitize_request_id(event.request_id),
        "tenant_id": event.tenant_id,
        "operator_id": _valid_operator_id(event.operator_id),
        "model": _export_model(metadata, event.provider),
        "locale": _optional_text(metadata.get("locale")),
        "entity_types": _entity_types_cell(metadata),
        "token_count": _token_count(metadata.get("token_count")),
        "decision": event.decision,
        "compliance_preset": _optional_text(metadata.get("compliance_preset")),
    }


def render_anonymization_csv(
    rows: Sequence[Mapping[str, Any]],
    *,
    bom: bool = False,
) -> bytes:
    """Serialize safe rows as UTF-8 CSV, with formula escaping on every cell."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(ANONYMIZATION_CSV_FIELDS))
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {field: escape_csv_formula(row.get(field)) for field in ANONYMIZATION_CSV_FIELDS}
        )
    payload = buffer.getvalue().encode("utf-8")
    if bom:
        return _UTF8_BOM + payload
    return payload


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
    are reported as 1. Raw values are never read. Names that are not
    entity-type labels are dropped.
    """
    merged: dict[str, int] = {}
    counts = metadata.get("entity_counts")
    if isinstance(counts, dict):
        for key, value in counts.items():
            if not isinstance(key, str) or _ENTITY_TYPE_RE.fullmatch(key) is None:
                continue
            try:
                merged[key] = int(value)
            except (TypeError, ValueError):
                continue
    listed = metadata.get("entity_types")
    if isinstance(listed, list):
        for item in listed:
            if isinstance(item, str) and _ENTITY_TYPE_RE.fullmatch(item) and item not in merged:
                merged[item] = 1
    return [{"type": key, "count": merged[key]} for key in sorted(merged)]


def anonymization_event_record(event: Any) -> dict[str, Any]:
    """One anonymization event row. Metadata only — never raw PII."""
    metadata = _metadata(event)
    model = _export_model(metadata, event.provider)
    return {
        "request_id": sanitize_request_id(event.request_id),
        "timestamp": iso_utc(event.timestamp),
        "tenant_id": event.tenant_id,
        "model": model,
        "locale": _optional_text(metadata.get("locale")),
        "decision": _optional_text(event.decision),
        "token_count": _token_count(metadata.get("token_count")),
        "entity_types": entity_type_counts(metadata),
        "row_id": getattr(event, "row_id", None),
    }


def encode_event_cursor(timestamp: str, row_id: int) -> str:
    """Keyset cursor: ISO-8601 UTC timestamp, a pipe, and the row id."""
    return f"{timestamp}|{row_id}"


def decode_event_cursor(cursor: str) -> tuple[datetime, int]:
    """Parse a keyset cursor. Raises ``ValueError`` when it is malformed."""
    stamp, separator, raw_id = cursor.rpartition("|")
    if not separator or not stamp or not raw_id:
        raise ValueError("cursor must be timestamp|id")
    row_id = int(raw_id)
    if row_id < 1:
        raise ValueError("cursor id must be positive")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC), row_id


async def iter_filtered_events(service: Any, **filters: Any) -> Any:
    """Yield every matching audit event using a timestamp+id keyset.

    Replaces offset paging so a concurrent insert cannot skip or repeat a
    row while a CSV stream is open.
    """
    cursor_timestamp: datetime | None = None
    cursor_id: int | None = None
    page = ANONYMIZATION_EXPORT_PAGE_SIZE
    while True:
        batch = await service.get_events(
            limit=page,
            offset=0,
            cursor_timestamp=cursor_timestamp,
            cursor_id=cursor_id,
            **filters,
        )
        if not batch:
            break
        for event in batch:
            yield event
        last = batch[-1]
        last_id = getattr(last, "row_id", None)
        if len(batch) < page or not isinstance(last_id, int):
            break
        if cursor_id == last_id and cursor_timestamp == last.timestamp:
            break
        cursor_timestamp = last.timestamp
        cursor_id = last_id


def anonymization_event_csv_row(record: dict[str, Any]) -> dict[str, str]:
    """CSV projection. Every cell is formula-escaped."""
    row: dict[str, str] = {}
    for key in ANONYMIZATION_EVENT_FIELDS:
        value = record.get(key)
        if key == "entity_types":
            rendered = json.dumps(value or [], separators=(",", ":"), ensure_ascii=False)
        elif value is None:
            rendered = ""
        else:
            rendered = str(value)
        row[key] = escape_csv_formula(rendered)
    return row


def csv_error_trailer(fieldnames: Sequence[str]) -> dict[str, str]:
    """Final CSV row appended when a stream fails after it has started."""
    row = {field: "" for field in fieldnames}
    if "request_id" in row:
        row["request_id"] = escape_csv_formula("#error")
    if "decision" in row:
        row["decision"] = "export_failed"
    return row
