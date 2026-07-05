"""Discovery audit event emission.

Provides:
- emit_risk_score_event: Audit event for risk score changes
"""

from __future__ import annotations

from typing import Any


def emit_risk_score_event(
    audit_logger: Any,
    service_name: str,
    previous_score: float | None = None,
    new_score: float | None = None,
    dimension_breakdown: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Emit a risk_score_updated audit event.

    Args:
        audit_logger: Audit logger with log_event method.
        service_name: Service name the score changed for.
        previous_score: Previous risk score (None for new services).
        new_score: New risk score (None if removed).
        dimension_breakdown: Per-dimension scores.

    Returns:
        Event dict.
    """
    event: dict[str, Any] = {
        "event_type": "risk_score_updated",
        "service_name": service_name,
        "previous_score": previous_score,
        "new_score": new_score,
        "dimension_breakdown": dimension_breakdown or {},
    }

    if audit_logger and hasattr(audit_logger, "log_event"):
        audit_logger.log_event(event)

    return event
