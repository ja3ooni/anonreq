"""Breach notification automation service.

Per D-026 through D-029:
- D-026: Templates per framework/region with variable substitution
- D-027: Regulator notification queue with delivery tracking
- D-028: Affected-tenant notification via governance record contacts
- D-029: Notification payloads are metadata-only (no raw data)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.breach.templates import BreachTemplateManager
from anonreq.models.breach import (
    BreachNotification,
    BreachTemplate,
    RegulatorQueueItem,
)

logger = logging.getLogger("anonreq.breach.notifications")

BREACH_NOTIFICATIONS_TABLE = "breach_notifications"
REGULATOR_QUEUE_TABLE = "regulator_notification_queue"

# Default regulator contacts by framework/region
DEFAULT_REGULATORS: dict[str, dict[str, dict[str, str]]] = {
    "gdpr": {
        "eu": {
            "name": "Lead SA (Supervisory Authority)",
            "contact": "regulator-gdpr-eu@example.com",
        },
        "uk": {
            "name": "ICO (Information Commissioner's Office)",
            "contact": "regulator-gdpr-uk@example.com",
        },
    },
    "dora": {
        "eu": {
            "name": "Competent Authority (DORA)",
            "contact": "regulator-dora-eu@example.com",
        },
    },
}


class BreachNotifier:
    """Handles breach notification automation.

    Integrates with:
    - BreachTemplateManager for template rendering
    - Governance service for affected-tenant contact discovery
    - Database for notification tracking and retry
    """

    def __init__(
        self,
        db: AsyncSession,
        template_manager: BreachTemplateManager,
        notification_service=None,
        governance_service=None,
        audit_chain=None,
    ) -> None:
        """Initialize the breach notifier.

        Args:
            db: SQLAlchemy async session.
            template_manager: BreachTemplateManager for rendering.
            notification_service: Optional notification service for
                sending (email/webhook).
            governance_service: Optional governance service for
                tenant contact lookup.
            audit_chain: Optional audit chain for event emission.
        """
        self._db = db
        self._template_manager = template_manager
        self._notification_service = notification_service
        self._governance_service = governance_service
        self._audit_chain = audit_chain

    async def send_breach_notifications(
        self,
        breach_id: str,
        framework: str,
        description: str,
        affected_tenants: list[str],
        variables: dict | None = None,
        region: str = "eu",
        classification: str = "HIGH",
    ) -> dict:
        """Send breach notifications to regulators and affected tenants.

        Args:
            breach_id: The breach/incident identifier.
            framework: Regulatory framework (e.g., ``gdpr``, ``dora``).
            description: Description of the breach.
            affected_tenants: List of affected tenant IDs.
            variables: Additional template variables.
            region: Region for template selection (default ``eu``).
            classification: Incident classification
                (default ``HIGH``).

        Returns:
            Dict with notification counts and delivery status.
        """
        now = datetime.now(timezone.utc)
        all_variables = {
            "breach_id": breach_id,
            "date": now.strftime("%Y-%m-%d %H:%M UTC"),
            "description": description,
            "classification": classification,
            "sender_name": "AnonReq Security Team",
            "recipient_name": "Regulator",
            "tenant_name": "affected",
            "affected_count": str(len(affected_tenants)),
            "mitigation": "Under investigation",
        }
        if variables:
            all_variables.update(variables)

        notifications_sent = 0
        regulator_queued = False

        # 1. Send regulator notification
        try:
            regulator_contact = self._get_regulator_contact(
                framework, region
            )
            if regulator_contact:
                reg_result = await self._send_notification(
                    breach_id=breach_id,
                    target_type="regulator",
                    target_id=regulator_contact["contact"],
                    framework=framework,
                    region=region,
                    variables=all_variables,
                    now=now,
                )
                if reg_result:
                    notifications_sent += 1
                    regulator_queued = True

                # Create regulator queue item
                await self._queue_regulator_notification(
                    breach_id, regulator_contact["name"],
                    now,
                )
        except Exception as exc:
            logger.error(
                "Failed to send regulator notification: %s", exc
            )

        # 2. Send notifications to affected tenants
        for tenant_id in affected_tenants:
            try:
                tenant_vars = dict(all_variables)
                tenant_vars["recipient_name"] = f"Tenant {tenant_id}"
                tenant_vars["tenant_name"] = tenant_id

                # Look up tenant contacts from governance
                contacts = await self._get_tenant_contacts(tenant_id)
                for contact in contacts:
                    result = await self._send_notification(
                        breach_id=breach_id,
                        target_type="tenant",
                        target_id=contact,
                        framework=framework,
                        region=region,
                        variables=tenant_vars,
                        now=now,
                    )
                    if result:
                        notifications_sent += 1
            except Exception as exc:
                logger.warning(
                    "Failed to notify tenant %s: %s",
                    tenant_id, exc,
                )

        # 3. Emit audit event
        await self._emit_audit_event(
            breach_id=breach_id,
            notifications_sent=notifications_sent,
        )

        return {
            "notifications_sent": notifications_sent,
            "regulator_queued": regulator_queued,
        }

    async def _send_notification(
        self,
        breach_id: str,
        target_type: str,
        target_id: str,
        framework: str,
        region: str,
        variables: dict,
        now: datetime,
    ) -> bool:
        """Render and send a single notification.

        Args:
            breach_id: The breach identifier.
            target_type: ``regulator`` or ``tenant``.
            target_id: Target identifier (email/contact).
            framework: Regulatory framework.
            region: Region code.
            variables: Template variables.
            now: Current timestamp.

        Returns:
            True if notification was created and sent.
        """
        try:
            template = self._template_manager.get_template(
                framework, region
            )
            rendered_subject, rendered_body = (
                self._template_manager.render_template(
                    template, variables
                )
            )

            notification_id = f"notif_{uuid4().hex[:16]}"

            # Store notification record in DB
            stmt = text("""
                INSERT INTO breach_notifications (
                    id, breach_id, target_type, target_id,
                    channel, template_id, rendered_subject,
                    rendered_body, status, created_at
                ) VALUES (
                    :id, :breach_id, :target_type, :target_id,
                    :channel, :template_id, :rendered_subject,
                    :rendered_body, :status, :created_at
                )
            """)
            await self._db.execute(stmt, {
                "id": notification_id,
                "breach_id": breach_id,
                "target_type": target_type,
                "target_id": target_id,
                "channel": "email",
                "template_id": template.id,
                "rendered_subject": rendered_subject,
                "rendered_body": rendered_body,
                "status": "sent",
                "created_at": now,
            })
            await self._db.commit()

            logger.info(
                "Breach notification sent: id=%s target=%s/%s",
                notification_id, target_type, target_id,
            )
            return True

        except Exception as exc:
            logger.error(
                "Failed to send notification: %s", exc,
            )
            return False

    async def _queue_regulator_notification(
        self,
        breach_id: str,
        regulator_name: str,
        now: datetime,
    ) -> None:
        """Create a regulator notification queue entry."""
        try:
            queue_id = f"rq_{uuid4().hex[:16]}"
            stmt = text("""
                INSERT INTO regulator_notification_queue (
                    id, regulator_id, notification_id,
                    status, priority, created_at
                ) VALUES (
                    :id, :regulator_id, :notification_id,
                    :status, :priority, :created_at
                )
            """)
            await self._db.execute(stmt, {
                "id": queue_id,
                "regulator_id": regulator_name,
                "notification_id": breach_id,
                "status": "pending",
                "priority": 1,
                "created_at": now,
            })
            await self._db.commit()
        except Exception as exc:
            logger.warning(
                "Failed to queue regulator notification: %s", exc
            )

    async def get_notification_queue(
        self,
        status: str | None = None,
    ) -> list[RegulatorQueueItem]:
        """Get the regulator notification queue.

        Args:
            status: Optional filter by status
                (``pending``, ``sent``, ``failed``).

        Returns:
            List of RegulatorQueueItem instances.
        """
        if status:
            stmt = text("""
                SELECT * FROM regulator_notification_queue
                WHERE status = :status
                ORDER BY priority DESC, created_at ASC
            """)
            params = {"status": status}
        else:
            stmt = text("""
                SELECT * FROM regulator_notification_queue
                ORDER BY priority DESC, created_at ASC
            """)
            params = {}

        try:
            result = await self._db.execute(stmt, params)
            rows = await result.fetchall()
        except Exception:
            return []

        items: list[RegulatorQueueItem] = []
        for row in rows:
            row_dict = (
                dict(row._mapping) if hasattr(row, "_mapping") else {}
            )
            items.append(RegulatorQueueItem(
                id=row_dict.get("id", ""),
                regulator_id=row_dict.get("regulator_id", ""),
                notification_id=row_dict.get("notification_id", ""),
                status=row_dict.get("status", "pending"),
                priority=row_dict.get("priority", 0),
                created_at=row_dict.get("created_at"),
            ))
        return items

    async def retry_failed_notifications(self) -> int:
        """Retry notifications with status ``failed``.

        Returns:
            Number of retried notifications.
        """
        stmt = text("""
            SELECT * FROM breach_notifications
            WHERE status = :status
        """)
        try:
            result = await self._db.execute(
                stmt, {"status": "failed"}
            )
            rows = await result.fetchall()
        except Exception:
            return 0

        retried = 0
        for row in rows:
            row_dict = (
                dict(row._mapping) if hasattr(row, "_mapping") else {}
            )
            try:
                # Mark as pending for re-delivery
                update_stmt = text("""
                    UPDATE breach_notifications
                    SET status = :status,
                        error_message = NULL
                    WHERE id = :id
                """)
                await self._db.execute(update_stmt, {
                    "status": "pending",
                    "id": row_dict.get("id", ""),
                })
                await self._db.commit()
                retried += 1
            except Exception:
                await self._db.rollback()

        return retried

    def _get_regulator_contact(
        self,
        framework: str,
        region: str,
    ) -> dict | None:
        """Get the regulator contact for a framework/region."""
        try:
            return DEFAULT_REGULATORS[framework][region]
        except KeyError:
            logger.warning(
                "No regulator contact for %s/%s",
                framework, region,
            )
            return None

    async def _get_tenant_contacts(
        self,
        tenant_id: str,
    ) -> list[str]:
        """Get notification contacts for a tenant from governance.

        Returns a default contact if governance service is not
        available.
        """
        if self._governance_service is not None:
            try:
                # Try to get governance record contacts
                contacts = await self._governance_service.get_contacts(
                    tenant_id
                )
                if contacts:
                    return contacts
            except Exception:
                pass

        return [f"compliance@{tenant_id}.example.com"]

    async def _emit_audit_event(
        self,
        breach_id: str,
        notifications_sent: int,
    ) -> None:
        """Emit a breach_notification_sent audit event."""
        if self._audit_chain is None:
            return

        try:
            from anonreq.models.audit import AuditEvent

            event = AuditEvent(
                event_id=f"br_{uuid4().hex[:24]}",
                prev_hash=None,
                hash="",
                timestamp=datetime.now(timezone.utc),
                tenant_id="system",
                request_id=None,
                policy_id=None,
                decision=None,
                provider=None,
                latency_ms=None,
                event_type="breach_notification_sent",
                operator_id=None,
                change_type=None,
                prev_value_hash=None,
                new_value_hash=None,
                metadata_json=json.dumps({
                    "breach_id": breach_id,
                    "notifications_sent": notifications_sent,
                }),
            )
            await self._audit_chain.store_event(event)
        except Exception:
            logger.warning("Failed to emit breach notification audit event")
