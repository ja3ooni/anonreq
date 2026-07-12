"""Tool governance audit event definitions and emitter.

Per D-013, D-014:
- 7 audit event types for all tool governance actions
- Structured metadata only — no raw tool arguments, no raw PII values
- Emitted via structured JSON to stdout (Phase 5 Audit Logger pattern)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ToolAuditEventType(Enum):
    """All 7 tool governance audit event types per D-013 and SECURITY-ACCEPTANCE.md."""

    TOOL_ALLOWED = "allowed"
    TOOL_BLOCKED = "blocked"
    TOOL_APPROVAL_REQUIRED = "approval_required"
    TOOL_APPROVAL_GRANTED = "approval_granted"
    TOOL_APPROVAL_DENIED = "approval_denied"
    TOOL_RESULT_PII_DETECTED = "result_pii_detected"
    TOOL_RESULT_RECONSTRUCTION_DETECTED = "result_reconstruction_detected"


@dataclass
class ToolAuditEvent:
    """Audit event for a single tool governance action.

    Contains metadata only — no raw tool arguments, no raw PII values,
    no token mappings. All fields are structured metadata for incident
    investigation.

    Attributes:
        event_type: The type of tool governance action.
        tool_name: Name of the tool being governed.
        provider: Provider identifier (e.g. openai, anthropic, host_mcp).
        domain: Tool domain — "model" or "host".
        permission: The permission decision (allow, block, etc.).
        tenant_id: Tenant identifier.
        session_id: Session identifier for correlation.
        timestamp: When the event occurred.
        risk_level: Risk classification (low, medium, high, critical).
        reconstruction_confidence: Confidence score 0.0-1.0 for
            reconstruction detection events.
        decision_reason: Human-readable reason for the decision.
        approved_by: Operator who approved/denied (for approval events).
        approval_note: Notes from the approving operator.

    Note:
        No field stores raw tool call arguments, raw PII values, or
        token mapping placeholders. This is enforced by the property
        test suite.
    """

    event_type: ToolAuditEventType
    tool_name: str
    provider: str
    domain: str = "model"
    permission: str = ""
    tenant_id: str = "default"
    session_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    risk_level: str | None = None
    reconstruction_confidence: float | None = None
    decision_reason: str | None = None
    approved_by: str | None = None
    approval_note: str | None = None

    """No raw tool arguments, raw PII values, or token mappings."""


# Explicitly forbidden keys — these must NEVER appear in serialized output.
# Tracked here for property test verification.
FORBIDDEN_AUDIT_KEYS: set[str] = {
    "tool_arguments",
    "raw_content",
    "pii_value",
    "token_value",
}


def tool_audit_event_to_dict(event: ToolAuditEvent) -> dict[str, Any]:
    """Serialize a ToolAuditEvent to a flat dict for the audit logger.

    Prefixes the event type with 'tool_' for the top-level ``event`` key.
    Excludes ``None`` values to keep output minimal. No raw tool arguments,
    no raw PII values, no token patterns are included.

    Args:
        event: The ToolAuditEvent to serialize.

    Returns:
        Flat dict suitable for ``audit_logger.info(event_name, **fields)``.
    """
    result: dict[str, Any] = {
        "event": f"tool_{event.event_type.value}",
        "tool_name": event.tool_name,
        "provider": event.provider,
        "domain": event.domain,
        "permission": event.permission,
        "tenant_id": event.tenant_id,
        "session_id": event.session_id,
        "timestamp": event.timestamp.isoformat(),
    }
    if event.risk_level is not None:
        result["risk_level"] = event.risk_level
    if event.reconstruction_confidence is not None:
        result["reconstruction_confidence"] = event.reconstruction_confidence
    if event.decision_reason is not None:
        result["decision_reason"] = event.decision_reason
    if event.approved_by is not None:
        result["approved_by"] = event.approved_by
    if event.approval_note is not None:
        result["approval_note"] = event.approval_note
    return result


def emit_tool_audit_event(event: ToolAuditEvent, audit_logger: Any) -> None:
    """Emit a tool governance audit event via the Phase 5 audit logger.

    Uses the established project pattern of
    ``audit_logger.info(event_name, **fields)`` where the first positional
    argument becomes the ``event`` key in structured JSON output and the
    remaining kwargs are the event fields.

    Args:
        event: The ToolAuditEvent to emit.
        audit_logger: A logger supporting ``.info(event_name, **fields)``.
            This is typically a structlog ``BoundLogger`` or stdlib
            ``logging.Logger`` instance passed by the caller.
    """
    event_dict = tool_audit_event_to_dict(event)
    event_name = event_dict.pop("event")
    audit_logger.info(event_name, **event_dict)
