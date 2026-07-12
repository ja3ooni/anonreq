"""DORA incident auto-escalation per criticality tier (D-016, D-017, D-018).

Per DORA regulation:
- CRITICAL service SLO breach → auto-create incident + notify
- IMPORTANT service SLO breach → log incident only
- STANDARD service breach → no escalation
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from anonreq.models.governance import (
    IncidentRecord,
    ServiceCriticality,
)

logger = logging.getLogger(__name__)

# In-memory store for incidents (replaced by PostgreSQL in prod)
_incident_store: list[IncidentRecord] = []


class IncidentManager:
    """Manages DORA ICT incident lifecycle with criticality-based escalation.

    Args:
        db: Async SQLAlchemy session (reserved for future PostgreSQL storage).
        notification_service: Service for sending notifications (must have
            an async ``notify`` method).
        emit_audit: Callable for emitting audit events. Receives
            ``event_type``, ``tenant_id``, and ``metadata_json`` kwargs.
    """

    def __init__(
        self,
        db: Any = None,
        notification_service: Any = None,
        emit_audit: Callable[..., Any] | None = None,
    ) -> None:
        self._db = db
        self._notification_service = notification_service
        self._emit_audit = emit_audit or _noop_audit

    def _next_id(self) -> str:
        return f"inc_{uuid.uuid4().hex[:12]}"

    async def create_incident(
        self,
        tenant_id: str,
        service_id: str,
        service_name: str,
        criticality: ServiceCriticality,
        severity: str,
        title: str,
        description: str,
    ) -> IncidentRecord:
        """Create a new incident record with auto-generated id and timestamp.

        Args:
            tenant_id: Tenant identifier.
            service_id: The service that experienced the incident.
            service_name: Human-readable service name.
            criticality: Service criticality tier.
            severity: Severity level (S1, S2, S3, etc.).
            title: Short incident title.
            description: Detailed incident description.

        Returns:
            The created IncidentRecord.
        """
        incident = IncidentRecord(
            id=self._next_id(),
            tenant_id=tenant_id,
            service_id=service_id,
            service_name=service_name,
            criticality=criticality,
            severity=severity,
            title=title,
            description=description,
            created_at=datetime.now(UTC),
        )
        _incident_store.append(incident)
        logger.info(
            "Incident created",
            extra={
                "incident_id": incident.id,
                "tenant_id": tenant_id,
                "criticality": criticality.value,
                "severity": severity,
            },
        )
        return incident

    async def escalate_if_needed(
        self,
        incident: IncidentRecord,
    ) -> IncidentRecord:
        """Escalate an incident based on its criticality tier.

        - CRITICAL: Sets escalated=True, calls notification service,
          emits ``dora_incident_created`` audit event.
        - IMPORTANT: Emits ``dora_incident_created`` audit event, no notify.
        - STANDARD: No action.

        Args:
            incident: The incident to evaluate and potentially escalate.

        Returns:
            The updated IncidentRecord (mutated in-place in the store).
        """
        if incident.criticality == ServiceCriticality.CRITICAL:
            incident.escalated = True
            incident.escalated_at = datetime.now(UTC)

            if self._notification_service is not None:
                crit_value = (
                    incident.criticality.value
                    if hasattr(incident.criticality, "value")
                    else incident.criticality
                )
                await self._notification_service.notify(
                    incident_id=incident.id,
                    tenant_id=incident.tenant_id,
                    title=incident.title,
                    criticality=crit_value,
                    severity=incident.severity,
                )
                incident.notified = True
                incident.notified_at = datetime.now(UTC)

            self._emit_audit(
                event_type="dora_incident_created",
                tenant_id=incident.tenant_id,
                metadata_json=incident.model_dump_json(),
            )
            logger.warning(
                "CRITICAL incident escalated with notification",
                extra={
                    "incident_id": incident.id,
                    "tenant_id": incident.tenant_id,
                    "service_id": incident.service_id,
                },
            )

        elif incident.criticality == ServiceCriticality.IMPORTANT:
            self._emit_audit(
                event_type="dora_incident_created",
                tenant_id=incident.tenant_id,
                metadata_json=incident.model_dump_json(),
            )
            logger.info(
                "IMPORTANT incident logged (no notification)",
                extra={
                    "incident_id": incident.id,
                    "tenant_id": incident.tenant_id,
                    "service_id": incident.service_id,
                },
            )

        else:
            logger.debug(
                "STANDARD incident — no escalation needed",
                extra={"incident_id": incident.id},
            )

        return incident

    async def auto_escalate_on_slo_breach(
        self,
        tenant_id: str,
        service_id: str,
        slo_metric: str,
        slo_value: float,
        threshold: float,
    ) -> IncidentRecord | None:
        """Handle an SLO breach by creating and escalating an incident.

        Currently assumes CRITICAL for all SLO breaches. In production,
        looks up the service's criticality from the provider inventory.

        Args:
            tenant_id: Tenant identifier.
            service_id: The service that breached its SLO.
            slo_metric: The SLO metric name (e.g. "P95 latency").
            slo_value: The actual measured value.
            threshold: The SLO threshold that was breached.

        Returns:
            The created incident, or None if no escalation occurred.
        """
        # In production: look up service criticality from provider inventory
        # For MVP: default to CRITICAL with contextual title
        criticality = ServiceCriticality.CRITICAL

        incident = await self.create_incident(
            tenant_id=tenant_id,
            service_id=service_id,
            service_name=service_id,  # In prod: look up from inventory
            criticality=criticality,
            severity="S1",
            title=f"SLO breach: {slo_metric} ({slo_value} vs threshold {threshold})",
            description=(
                f"SLO metric '{slo_metric}' breached — "
                f"value={slo_value}, threshold={threshold}"
            ),
        )

        result = await self.escalate_if_needed(incident)
        return result

    async def list_incidents(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
        criticality: ServiceCriticality | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[IncidentRecord]:
        """List incidents with optional filtering.

        Args:
            tenant_id: Filter by tenant.
            status: Filter by status (e.g. "open", "resolved").
            criticality: Filter by criticality tier.
            skip: Number of records to skip (pagination).
            limit: Maximum number of records to return.

        Returns:
            Filtered list of incidents.
        """
        result = list(_incident_store)

        if tenant_id is not None:
            result = [i for i in result if i.tenant_id == tenant_id]
        if status is not None:
            result = [i for i in result if i.status == status]
        if criticality is not None:
            result = [i for i in result if i.criticality == criticality]

        return result[skip : skip + limit]

    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str,
    ) -> IncidentRecord | None:
        """Resolve an incident by setting its status and resolved_at.

        Args:
            incident_id: The incident identifier.
            resolution: Resolution description.

        Returns:
            The updated incident, or None if not found.
        """
        for incident in _incident_store:
            if incident.id == incident_id:
                incident.status = "resolved"
                incident.resolved_at = datetime.now(UTC)
                logger.info(
                    "Incident resolved",
                    extra={
                        "incident_id": incident_id,
                        "resolution": resolution,
                    },
                )
                return incident
        return None


def _noop_audit(**kwargs: Any) -> None:
    """No-op audit emitter for tests without audit infrastructure."""
    pass
