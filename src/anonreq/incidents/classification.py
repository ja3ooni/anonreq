"""Incident classification per D-008.

Severity tiers:
- CRITICAL (S1): Data exposure — notify immediate
- HIGH (S2): SLO breach with high impact — 24h response
- MEDIUM (S3): SLO breach — 72h response
- LOW: Informational — next review cycle
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from anonreq.models.fairness import INCIDENT_RESPONSE_TIMES, IncidentSeverity


class IncidentClassifier:
    """Rule-based incident severity classification (D-008).

    Classifies incidents based on type, impact, data exposure flag,
    and SLO breach status. Pure logic — no external dependencies.
    """

    @staticmethod
    def classify(
        incident_type: str,  # noqa: ARG004 — used by callers for classification context
        impact: str = "low",
        data_exposure: bool = False,
        slo_breach: bool = False,
    ) -> IncidentSeverity:
        """Classify an incident into a severity tier.

        Rules:
        - data_exposure → CRITICAL (S1)
        - slo_breach + impact == "high" → HIGH (S2)
        - slo_breach → MEDIUM (S3)
        - else → LOW

        Args:
            incident_type: Type/category of the incident.
            impact: Impact level ("low", "medium", "high").
            data_exposure: Whether PII data was exposed.
            slo_breach: Whether an SLO was breached.

        Returns:
            Classified IncidentSeverity.
        """
        if data_exposure:
            return IncidentSeverity.CRITICAL
        if slo_breach:
            if impact == "high":
                return IncidentSeverity.HIGH
            return IncidentSeverity.MEDIUM
        return IncidentSeverity.LOW

    @staticmethod
    def get_response_time(severity: IncidentSeverity) -> str:
        """Get the required response time for a severity level.

        Args:
            severity: The incident severity.

        Returns:
            Response time requirement string.
        """
        return INCIDENT_RESPONSE_TIMES.get(severity.name, "next_review")

    @staticmethod
    def should_notify_immediate(severity: IncidentSeverity) -> bool:
        """Whether immediate notification is required.

        Only CRITICAL incidents require immediate notification.

        Args:
            severity: The incident severity.

        Returns:
            True if immediate notification is needed.
        """
        return severity == IncidentSeverity.CRITICAL

    @staticmethod
    def create_incident_record(
        incident_id: str,
        severity: IncidentSeverity,
        incident_type: str,
        entity_type: str,
        drift_amount: float,
        baseline_recall: float,
        production_recall: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an incident record dict for audit logging.

        Args:
            incident_id: Unique incident identifier.
            severity: Classified severity.
            incident_type: Type of incident.
            entity_type: Entity type involved.
            drift_amount: Measured drift amount.
            baseline_recall: Baseline recall value.
            production_recall: Production recall value.
            metadata: Optional additional context.

        Returns:
            Incident record as a dict suitable for audit logging.
        """
        from datetime import datetime

        return {
            "incident_id": incident_id,
            "severity": severity.name,
            "severity_value": int(severity),
            "response_time": INCIDENT_RESPONSE_TIMES.get(severity.name, "next_review"),
            "incident_type": incident_type,
            "entity_type": entity_type,
            "drift_amount": drift_amount,
            "baseline_recall": baseline_recall,
            "production_recall": production_recall,
            "detected_at": datetime.now(UTC).isoformat(),
            "notify_immediate": severity == IncidentSeverity.CRITICAL,
            "metadata": metadata or {},
        }
