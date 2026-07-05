"""DSAR workflow: submit → verify → fulfill with status tracking.

Per D-021 through D-025:
- D-021: DSAR intake with status tracking
- D-022: Calls erasure service for ERASURE requests
- D-023: Calls restriction service for RESTRICTION requests
- D-024: Legal Hold check prevents erasure when hold active
- D-025: Returns subject_status: deleted, processing_restricted, or legal_hold
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.dsar import (
    DsarRequest,
    DsarRequestType,
    DsarResult,
    SubjectStatus,
)
from anonreq.models.audit import AuditEvent

logger = logging.getLogger("anonreq.dsar.workflow")


class DsarWorkflow:
    """Manages the DSAR lifecycle.

    Supports submit → verify → fulfill workflow with integration
    to erasure, restriction, and Legal Hold services.
    """

    DSAR_TABLE = "dsar_requests"

    def __init__(
        self,
        db: AsyncSession,
        erasure_service=None,
        restriction_service=None,
        legal_hold_manager=None,
        audit_chain=None,
    ) -> None:
        """Initialize the DSAR workflow.

        Args:
            db: SQLAlchemy async session.
            erasure_service: Optional DataErasureService for
                ERASURE requests.
            restriction_service: Optional DataRestrictionService for
                RESTRICTION requests.
            legal_hold_manager: Optional LegalHoldManager for Legal
                Hold interception.
            audit_chain: Optional AuditChain for event emission.
        """
        self._db = db
        self._erasure_service = erasure_service
        self._restriction_service = restriction_service
        self._legal_hold_manager = legal_hold_manager
        self._audit_chain = audit_chain

    async def submit_request(
        self,
        tenant_id: str,
        subject_id: str,
        request_type: DsarRequestType,
        verification_details: dict | None = None,
        notes: str | None = None,
    ) -> DsarRequest:
        """Submit a new DSAR request.

        Creates the request with status ``pending_verification`` and
        emits a ``dsar_request_received`` audit event.

        Args:
            tenant_id: The tenant the data subject belongs to.
            subject_id: The data subject identifier.
            request_type: Type of DSAR request.
            verification_details: Optional verification metadata.
            notes: Optional notes for the request.

        Returns:
            The created DsarRequest.
        """
        now = datetime.now(timezone.utc)
        request_id = f"dsar_{uuid4().hex[:16]}"

        request = DsarRequest(
            id=request_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            request_type=request_type,
            status="pending_verification",
            verification_details=verification_details,
            submitted_at=now,
            notes=notes,
        )

        # Store in PostgreSQL
        stmt = text("""
            INSERT INTO dsar_requests (
                id, tenant_id, subject_id, request_type,
                status, verification_details, submitted_at, notes
            ) VALUES (
                :id, :tenant_id, :subject_id, :request_type,
                :status, :verification_details, :submitted_at, :notes
            )
        """)
        try:
            await self._db.execute(stmt, {
                "id": request.id,
                "tenant_id": request.tenant_id,
                "subject_id": request.subject_id,
                "request_type": request.request_type.value,
                "status": request.status,
                "verification_details": str(request.verification_details or {}),
                "submitted_at": request.submitted_at,
                "notes": request.notes,
            })
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            logger.error("Failed to submit DSAR request: %s", exc)
            raise RuntimeError(
                f"Failed to submit DSAR request: {exc}"
            ) from exc

        # Emit audit event
        await self._emit_audit_event(
            event_type="dsar_request_received",
            tenant_id=tenant_id,
            metadata={
                "request_id": request_id,
                "request_type": request_type.value,
                "subject_id": subject_id,
            },
        )

        logger.info(
            "DSAR request submitted: id=%s type=%s tenant=%s",
            request_id, request_type.value, tenant_id,
        )
        return request

    async def verify_request(
        self,
        request_id: str,
        verified_by: str,
    ) -> DsarRequest:
        """Verify a DSAR request and transition to processing.

        Args:
            request_id: The DSAR request ID.
            verified_by: Identity of the verifier.

        Returns:
            The updated DsarRequest with status ``processing``.

        Raises:
            ValueError: If the request is not found.
        """
        now = datetime.now(timezone.utc)
        stmt = text("""
            UPDATE dsar_requests
            SET status = :status,
                verified_by = :verified_by,
                verified_at = :verified_at
            WHERE id = :id
        """)
        try:
            result = await self._db.execute(stmt, {
                "status": "processing",
                "verified_by": verified_by,
                "verified_at": now,
                "id": request_id,
            })
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise ValueError(f"Failed to verify DSAR request: {request_id}")

        if result.rowcount == 0:
            raise ValueError(f"DSAR request not found: {request_id}")

        return DsarRequest(
            id=request_id,
            tenant_id="",
            subject_id="",
            request_type=DsarRequestType.ACCESS,
            status="processing",
            verified_by=verified_by,
            verified_at=now,
        )

    async def fulfill_request(
        self,
        request_id: str,
        fulfilled_by: str,
    ) -> DsarResult:
        """Fulfill a DSAR request.

        Loads the request and performs the appropriate action:
        - ERASURE: erases subject data (unless under Legal Hold)
        - RESTRICTION: restricts subject processing
        - Other types: currently returns ACTIVE (stub)

        Args:
            request_id: The DSAR request ID.
            fulfilled_by: Identity of the fulfiller.

        Returns:
            DsarResult with the subject_status.

        Raises:
            ValueError: If request not found.
        """
        request = await self._get_request(request_id)
        if request is None:
            raise ValueError(f"DSAR request not found: {request_id}")

        now = datetime.now(timezone.utc)
        subject_status: SubjectStatus | None = None
        summary = ""

        # Check Legal Hold first — blocks erasure
        if request.request_type == DsarRequestType.ERASURE:
            on_hold = False
            if self._legal_hold_manager is not None:
                try:
                    on_hold = await self._legal_hold_manager.is_on_hold(
                        request.tenant_id,
                        record_id=request.subject_id,
                    )
                except Exception:
                    logger.warning(
                        "Legal Hold check failed for %s", request_id
                    )

            if on_hold:
                subject_status = SubjectStatus.LEGAL_HOLD
                summary = (
                    "Erasure blocked — subject is under Legal Hold"
                )

        # Perform erasure
        if (
            request.request_type == DsarRequestType.ERASURE
            and subject_status is None
        ):
            if self._erasure_service is not None:
                try:
                    await self._erasure_service.erase_subject_data(
                        request.subject_id, db=self._db
                    )
                except Exception as exc:
                    logger.error(
                        "Erasure failed for %s: %s", request_id, exc
                    )
                    raise RuntimeError(
                        f"Erasure failed for {request_id}: {exc}"
                    ) from exc
            subject_status = SubjectStatus.DELETED
            summary = f"Subject {request.subject_id} data erased successfully"

        # Perform restriction
        elif request.request_type == DsarRequestType.RESTRICTION:
            if self._restriction_service is not None:
                try:
                    await self._restriction_service.restrict_subject(
                        request.tenant_id, request.subject_id
                    )
                except Exception as exc:
                    logger.error(
                        "Restriction failed for %s: %s",
                        request_id, exc,
                    )
                    raise RuntimeError(
                        f"Restriction failed for {request_id}: {exc}"
                    ) from exc
            subject_status = SubjectStatus.PROCESSING_RESTRICTED
            summary = f"Subject {request.subject_id} processing restricted"

        # Other request types (stub)
        elif subject_status is None:
            subject_status = SubjectStatus.ACTIVE
            summary = (
                f"Request type {request.request_type.value} fulfilled "
                f"— no automated action"
            )

        # Update request record
        await self._update_request_fulfillment(
            request_id, subject_status, fulfilled_by, now
        )

        # Emit audit event
        await self._emit_audit_event(
            event_type="dsar_completed",
            tenant_id=request.tenant_id,
            metadata={
                "request_id": request_id,
                "request_type": request.request_type.value,
                "subject_status": subject_status.value,
            },
        )

        logger.info(
            "DSAR request fulfilled: id=%s status=%s",
            request_id, subject_status.value,
        )

        return DsarResult(
            request_id=request_id,
            subject_status=subject_status,
            summary=summary,
            fulfilled_at=now,
        )

    async def get_request_status(
        self,
        request_id: str,
    ) -> DsarRequest | None:
        """Get the current status of a DSAR request.

        Args:
            request_id: The DSAR request ID.

        Returns:
            The DsarRequest if found, None otherwise.
        """
        return await self._get_request(request_id)

    async def list_requests(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[DsarRequest]:
        """List DSAR requests with optional filters.

        Args:
            tenant_id: Optional tenant filter.
            status: Optional status filter.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of matching DsarRequest instances.
        """
        conditions: list[str] = []
        params: dict = {}

        if tenant_id:
            conditions.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        stmt = text(f"""
            SELECT * FROM dsar_requests
            WHERE {where_clause}
            ORDER BY submitted_at DESC
            LIMIT :limit OFFSET :skip
        """)
        params["limit"] = limit
        params["skip"] = skip

        try:
            result = await self._db.execute(stmt, params)
            rows = await result.fetchall()
        except Exception:
            return []

        requests: list[DsarRequest] = []
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
            requests.append(self._row_to_request(row_dict))

        return requests

    async def _get_request(
        self, request_id: str
    ) -> DsarRequest | None:
        """Get a DSAR request by ID from PostgreSQL."""
        stmt = text(
            "SELECT * FROM dsar_requests WHERE id = :id"
        )
        try:
            result = await self._db.execute(stmt, {"id": request_id})
            row = await result.fetchone()
        except Exception:
            return None

        if row is None:
            return None

        row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
        return self._row_to_request(row_dict)

    async def _update_request_fulfillment(
        self,
        request_id: str,
        subject_status: SubjectStatus,
        fulfilled_by: str,
        fulfilled_at: datetime,
    ) -> None:
        """Update a DSAR request with fulfillment results."""
        stmt = text("""
            UPDATE dsar_requests
            SET status = :status,
                result = :result,
                fulfilled_by = :fulfilled_by,
                fulfilled_at = :fulfilled_at
            WHERE id = :id
        """)
        try:
            await self._db.execute(stmt, {
                "status": "fulfilled",
                "result": subject_status.value,
                "fulfilled_by": fulfilled_by,
                "fulfilled_at": fulfilled_at,
                "id": request_id,
            })
            await self._db.commit()
        except Exception:
            await self._db.rollback()

    @staticmethod
    def _row_to_request(row_dict: dict) -> DsarRequest:
        """Convert a DB row dict to a DsarRequest."""
        request_type_str = row_dict.get("request_type", "ACCESS")
        try:
            request_type = DsarRequestType(request_type_str)
        except ValueError:
            request_type = DsarRequestType.ACCESS

        result_str = row_dict.get("result")
        subject_status: SubjectStatus | None = None
        if result_str:
            try:
                subject_status = SubjectStatus(result_str)
            except ValueError:
                pass

        return DsarRequest(
            id=row_dict.get("id", ""),
            tenant_id=row_dict.get("tenant_id", ""),
            subject_id=row_dict.get("subject_id", ""),
            request_type=request_type,
            status=row_dict.get("status", "pending_verification"),
            verified_by=row_dict.get("verified_by"),
            fulfilled_by=row_dict.get("fulfilled_by"),
            submitted_at=row_dict.get("submitted_at"),
            verified_at=row_dict.get("verified_at"),
            fulfilled_at=row_dict.get("fulfilled_at"),
            result=subject_status,
            notes=row_dict.get("notes"),
        )

    async def _emit_audit_event(
        self,
        event_type: str,
        tenant_id: str,
        metadata: dict | None = None,
    ) -> None:
        """Emit an audit event if audit_chain is available."""
        if self._audit_chain is None:
            return

        try:
            import json

            event = AuditEvent(
                event_id=f"dsar_{uuid4().hex[:24]}",
                prev_hash=None,
                hash="",
                timestamp=datetime.now(timezone.utc),
                tenant_id=tenant_id,
                request_id=None,
                policy_id=None,
                decision=None,
                provider=None,
                latency_ms=None,
                event_type=event_type,
                operator_id=None,
                change_type=None,
                prev_value_hash=None,
                new_value_hash=None,
                metadata_json=json.dumps(metadata or {}),
            )
            await self._audit_chain.store_event(event)
        except Exception:
            logger.warning(
                "Failed to emit audit event %s", event_type,
            )
