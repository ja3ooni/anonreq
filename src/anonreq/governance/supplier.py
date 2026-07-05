"""Third-party AI supplier governance with Phase 14 lifecycle integration.

Per D-012 through D-016:
- Provider inventory with contract/risk/review status (D-012)
- Provider review cycle defaults to 365 days (D-013)
- Uses Phase 14 lifecycle stages (D-014)
- Risk re-evaluation triggers (D-015)
- Overdue reviews surfaced in governance status (D-016)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.lineage import SupplierGovernanceRecord

logger = logging.getLogger("anonreq.governance.supplier")

SUPPLIER_TABLE = "supplier_governance"
"""Database table name for supplier governance records."""

SUPPLIER_REVIEW_TRIGGERS: list[str] = [
    "model_change",
    "tos_change",
    "data_residency_change",
    "ai_act_reclassification",
    "security_incident",
]
"""Valid risk re-evaluation triggers per D-015.

- ``model_change``: Provider released a new model version
- ``tos_change``: Provider updated terms of service
- ``data_residency_change``: Provider changed data processing location
- ``ai_act_reclassification``: New EU AI Act classification applies
- ``security_incident``: Provider experienced a security incident
"""


class SupplierGovernance:
    """Supplier governance managing third-party AI provider relationships.

    Integrates with Phase 14 lifecycle service for stage tracking
    (DRAFT → APPROVED → PRODUCTION) and provides overdue review
    detection for compliance monitoring.

    Per D-016: Overdue reviews affect the governance status endpoint.
    """

    def __init__(
        self,
        db: AsyncSession,
        lifecycle_manager=None,
    ) -> None:
        """Initialize the supplier governance manager.

        Args:
            db: SQLAlchemy async session.
            lifecycle_manager: Optional Phase 14 lifecycle manager.
                If provided, supplier creation creates a lifecycle
                object for stage tracking.
        """
        self._db = db
        self._lifecycle_manager = lifecycle_manager

    async def create_supplier(
        self,
        name: str,
        provider_type: str,
        contract_status: str = "active",
        risk_status: str = "low",
    ) -> SupplierGovernanceRecord:
        """Create a new supplier governance record.

        Args:
            name: Supplier/provider name.
            provider_type: Type of provider (e.g., ``llm``, ``embedding``).
            contract_status: Contract status (e.g., ``active``,
                ``negotiating``, ``terminated``).
            risk_status: Risk status (e.g., ``low``, ``medium``,
                ``high``, ``critical``).

        Returns:
            The created SupplierGovernanceRecord with generated ID
            and timestamps.

        Raises:
            RuntimeError: If database insert fails.
        """
        now = datetime.now(timezone.utc)
        record_id = f"sup_{uuid4().hex[:16]}"

        # Create lifecycle object if manager is available
        lifecycle_obj_id = ""
        if self._lifecycle_manager is not None:
            try:
                lifecycle_obj_id = await self._lifecycle_manager.create_object(
                    name=name,
                    object_type="supplier",
                    stage="DRAFT",
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create lifecycle object for supplier %s: %s",
                    name, exc,
                )

        # Calculate next review date
        next_review = now + timedelta(days=365)

        # Store in PostgreSQL
        stmt = text("""
            INSERT INTO supplier_governance (
                id, name, provider_type, contract_status,
                risk_status, review_cycle_days,
                last_review_date, next_review_date,
                lifecycle_object_id, risk_re_evaluation_triggers,
                created_at, updated_at
            ) VALUES (
                :id, :name, :provider_type, :contract_status,
                :risk_status, :review_cycle_days,
                :last_review_date, :next_review_date,
                :lifecycle_object_id, :risk_re_evaluation_triggers,
                :created_at, :updated_at
            )
        """)
        params = {
            "id": record_id,
            "name": name,
            "provider_type": provider_type,
            "contract_status": contract_status,
            "risk_status": risk_status,
            "review_cycle_days": 365,
            "last_review_date": None,
            "next_review_date": next_review,
            "lifecycle_object_id": lifecycle_obj_id,
            "risk_re_evaluation_triggers": "",
            "created_at": now,
            "updated_at": now,
        }

        try:
            await self._db.execute(stmt, params)
            await self._db.commit()
            logger.info(
                "Supplier created: id=%s name=%s type=%s",
                record_id, name, provider_type,
            )
        except Exception as exc:
            await self._db.rollback()
            logger.error("Failed to create supplier: %s", exc)
            raise RuntimeError(f"Failed to create supplier: {exc}") from exc

        return SupplierGovernanceRecord(
            id=record_id,
            name=name,
            provider_type=provider_type,
            contract_status=contract_status,
            risk_status=risk_status,
            review_cycle_days=365,
            next_review_date=next_review,
            lifecycle_object_id=lifecycle_obj_id,
            created_at=now,
            updated_at=now,
        )

    async def get_supplier(
        self,
        supplier_id: str,
    ) -> SupplierGovernanceRecord | None:
        """Get a supplier by ID.

        Args:
            supplier_id: The supplier record ID.

        Returns:
            The SupplierGovernanceRecord if found, None otherwise.
        """
        stmt = text(
            "SELECT * FROM supplier_governance WHERE id = :id"
        )
        try:
            result = await self._db.execute(stmt, {"id": supplier_id})
            row = await result.fetchone()
        except Exception:
            return None

        if row is None:
            return None

        row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
        return self._row_to_record(row_dict)

    async def list_suppliers(
        self,
        risk_status: str | None = None,
        contract_status: str | None = None,
    ) -> list[SupplierGovernanceRecord]:
        """List suppliers with optional filtering.

        Args:
            risk_status: Optional filter by risk status.
            contract_status: Optional filter by contract status.

        Returns:
            List of matching SupplierGovernanceRecord instances.
        """
        conditions: list[str] = []
        params: dict = {}

        if risk_status is not None:
            conditions.append("risk_status = :risk_status")
            params["risk_status"] = risk_status
        if contract_status is not None:
            conditions.append("contract_status = :contract_status")
            params["contract_status"] = contract_status

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        stmt = text(f"""
            SELECT * FROM supplier_governance
            WHERE {where_clause}
            ORDER BY created_at DESC
        """)

        try:
            result = await self._db.execute(stmt, params)
            rows = await result.fetchall()
        except Exception:
            return []

        records: list[SupplierGovernanceRecord] = []
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
            records.append(self._row_to_record(row_dict))

        return records

    async def get_overdue_reviews(
        self,
    ) -> list[SupplierGovernanceRecord]:
        """Get suppliers with overdue reviews.

        A review is overdue when ``next_review_date`` is in the past
        and the supplier's contract is active.

        Returns:
            List of SupplierGovernanceRecord instances with
            overdue reviews.
        """
        now = datetime.now(timezone.utc)
        stmt = text("""
            SELECT * FROM supplier_governance
            WHERE next_review_date < :now
              AND contract_status = 'active'
            ORDER BY next_review_date ASC
        """)
        try:
            result = await self._db.execute(stmt, {"now": now})
            rows = await result.fetchall()
        except Exception:
            return []

        records: list[SupplierGovernanceRecord] = []
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
            records.append(self._row_to_record(row_dict))

        return records

    async def trigger_risk_re_evaluation(
        self,
        supplier_id: str,
        trigger: str,
    ) -> SupplierGovernanceRecord:
        """Trigger a risk re-evaluation for a supplier.

        Per D-015: Updates risk_status to ``re_evaluation_required``
        and records the trigger.

        Args:
            supplier_id: The supplier record ID.
            trigger: The re-evaluation trigger. Must be one of
                ``SUPPLIER_REVIEW_TRIGGERS``.

        Returns:
            The updated SupplierGovernanceRecord.

        Raises:
            ValueError: If supplier not found or trigger is invalid.
        """
        if trigger not in SUPPLIER_REVIEW_TRIGGERS:
            raise ValueError(
                f"Invalid trigger: {trigger}. Must be one of "
                f"{SUPPLIER_REVIEW_TRIGGERS}"
            )

        # Check supplier exists
        supplier = await self.get_supplier(supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier not found: {supplier_id}")

        # Update risk status and add trigger
        now = datetime.now(timezone.utc)

        # Read existing triggers and append new one
        existing_triggers = supplier.risk_re_evaluation_triggers or []
        if trigger not in existing_triggers:
            existing_triggers.append(trigger)

        update_stmt = text("""
            UPDATE supplier_governance
            SET risk_status = 're_evaluation_required',
                risk_re_evaluation_triggers = :triggers,
                updated_at = :updated_at
            WHERE id = :id
        """)
        try:
            await self._db.execute(update_stmt, {
                "triggers": ",".join(existing_triggers),
                "updated_at": now,
                "id": supplier_id,
            })
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            raise RuntimeError(
                f"Failed to trigger risk re-evaluation: {exc}"
            ) from exc

        return SupplierGovernanceRecord(
            id=supplier_id,
            name=supplier.name,
            provider_type=supplier.provider_type,
            contract_status=supplier.contract_status,
            risk_status="re_evaluation_required",
            review_cycle_days=supplier.review_cycle_days,
            next_review_date=supplier.next_review_date,
            lifecycle_object_id=supplier.lifecycle_object_id,
            risk_re_evaluation_triggers=existing_triggers,
            created_at=supplier.created_at,
            updated_at=now,
        )

    async def complete_review(
        self,
        supplier_id: str,
        risk_status: str,
    ) -> SupplierGovernanceRecord:
        """Complete a review for a supplier.

        Updates ``last_review_date``, ``next_review_date``, and
        ``risk_status``.

        Args:
            supplier_id: The supplier record ID.
            risk_status: Updated risk status after review.

        Returns:
            The updated SupplierGovernanceRecord.

        Raises:
            ValueError: If supplier not found.
        """
        supplier = await self.get_supplier(supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier not found: {supplier_id}")

        now = datetime.now(timezone.utc)
        next_review = now + timedelta(days=supplier.review_cycle_days)

        update_stmt = text("""
            UPDATE supplier_governance
            SET last_review_date = :last_review_date,
                next_review_date = :next_review_date,
                risk_status = :risk_status,
                risk_re_evaluation_triggers = '',
                updated_at = :updated_at
            WHERE id = :id
        """)
        try:
            await self._db.execute(update_stmt, {
                "last_review_date": now,
                "next_review_date": next_review,
                "risk_status": risk_status,
                "updated_at": now,
                "id": supplier_id,
            })
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            raise RuntimeError(
                f"Failed to complete review: {exc}"
            ) from exc

        return SupplierGovernanceRecord(
            id=supplier_id,
            name=supplier.name,
            provider_type=supplier.provider_type,
            contract_status=supplier.contract_status,
            risk_status=risk_status,
            review_cycle_days=supplier.review_cycle_days,
            last_review_date=now,
            next_review_date=next_review,
            lifecycle_object_id=supplier.lifecycle_object_id,
            created_at=supplier.created_at,
            updated_at=now,
        )

    @staticmethod
    def _row_to_record(row_dict: dict) -> SupplierGovernanceRecord:
        """Convert a DB row dict to a SupplierGovernanceRecord.

        Handles comma-separated trigger strings and string-to-datetime
        conversion.

        Args:
            row_dict: Row dict from SQLAlchemy result.

        Returns:
            SupplierGovernanceRecord instance.
        """
        triggers_str = row_dict.get("risk_re_evaluation_triggers", "") or ""
        triggers = [t.strip() for t in triggers_str.split(",") if t.strip()]

        return SupplierGovernanceRecord(
            id=row_dict.get("id", ""),
            name=row_dict.get("name", ""),
            provider_type=row_dict.get("provider_type", ""),
            contract_status=row_dict.get("contract_status", "active"),
            risk_status=row_dict.get("risk_status", "low"),
            review_cycle_days=row_dict.get("review_cycle_days", 365),
            last_review_date=row_dict.get("last_review_date"),
            next_review_date=row_dict.get("next_review_date"),
            lifecycle_object_id=row_dict.get("lifecycle_object_id", ""),
            risk_re_evaluation_triggers=triggers,
            created_at=row_dict.get("created_at"),
            updated_at=row_dict.get("updated_at"),
        )
