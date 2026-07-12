"""Runtime fairness drift monitoring for post-deployment surveillance.

Per D-002, D-006, D-007:
- Monitors production PII detection quality against fairness baseline
- Compares 60-minute production window against baseline evaluation
- Creates incidents when drift exceeds threshold
- Emits fairness_drift_detected audit events
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import Integer, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.incidents.classification import IncidentClassifier
from anonreq.models.fairness import (
    FairnessEvaluation,
    ProductionMetricModel,
)

logger = logging.getLogger("anonreq.fairness.monitoring")

DEFAULT_DRIFT_THRESHOLD = 0.02


class FairnessMonitor:
    """Monitors production detection quality drift against baseline.

    Records per-session detection metrics and compares rolling
    60-minute windows against the baseline fairness evaluation.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        incident_classifier: IncidentClassifier | None = None,
        baseline_evaluation: FairnessEvaluation | None = None,
        drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    ) -> None:
        """Initialize the monitor.

        Args:
            engine: Async SQLAlchemy engine for metric storage.
            incident_classifier: Optional classifier for drift incidents.
            baseline_evaluation: Baseline fairness evaluation to compare against.
            drift_threshold: Maximum acceptable drift from baseline (default 0.02).
        """
        self._engine = engine
        self._session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._incident_classifier = incident_classifier or IncidentClassifier()
        self._baseline: FairnessEvaluation | None = baseline_evaluation
        self.drift_threshold = drift_threshold

    async def record_production_metric(
        self,
        tenant_id: str,
        entity_type: str,
        detected: bool,
        demographic_group: str,
    ) -> None:
        """Record a single production detection metric.

        Args:
            tenant_id: Tenant identifier.
            entity_type: PII entity type (e.g., "PERSON").
            detected: Whether the entity was correctly detected.
            demographic_group: Demographic group of the request.
        """
        async with self._session_factory() as session, session.begin():
            metric = ProductionMetricModel(
                tenant_id=tenant_id,
                entity_type=entity_type,
                demographic_group=demographic_group,
                detected=detected,
                recorded_at=datetime.now(UTC),
            )
            session.add(metric)

    async def set_baseline(self, evaluation: FairnessEvaluation) -> None:
        """Update the baseline from a completed fairness evaluation.

        Args:
            evaluation: The evaluation to use as the new baseline.
        """
        self._baseline = evaluation

    async def check_drift(
        self,
        window_minutes: int = 60,
        emit_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Check for fairness drift in the latest production window.

        Computes production recall for a rolling time window and compares
        against baseline evaluation. Creates incidents for any drift
        exceeding the threshold.

        Args:
            window_minutes: Size of the production window in minutes (default 60).
            emit_event: Optional callback for audit event emission.

        Returns:
            List of drift alert dicts:
            [{"entity_type": "...", "drift": float, "baseline_recall": float,
              "production_recall": float, "severity": str, "incident_id": str}]
        """
        if self._baseline is None:
            logger.warning("No baseline set — returning empty drift results")
            return []

        window_start = datetime.now(UTC) - timedelta(minutes=window_minutes)

        alerts: list[dict[str, Any]] = []

        for eval_result in self._baseline.results:
            entity_type = eval_result.entity_type
            baseline_recall = eval_result.overall_recall

            async with self._session_factory() as session:
                stmt = select(
                    func.count(ProductionMetricModel.id),
                    func.sum(
                        cast(ProductionMetricModel.detected, Integer)
                    ),
                ).where(
                    and_(
                        ProductionMetricModel.entity_type == entity_type,
                        ProductionMetricModel.recorded_at >= window_start,
                    )
                )
                row = await session.execute(stmt)
                total, detected_sum = row.one()
                total = total or 0
                detected = detected_sum or 0

            if total == 0:
                continue

            production_recall = detected / total
            drift = abs(production_recall - baseline_recall)

            if drift > self.drift_threshold:
                sev = self._incident_classifier.classify(
                    incident_type="fairness_drift",
                    impact="medium" if drift > self.drift_threshold * 2 else "low",
                    data_exposure=False,
                    slo_breach=True,
                )

                incident_id = f"inc_{uuid4().hex[:16]}"
                self._incident_classifier.create_incident_record(
                    incident_id=incident_id,
                    severity=sev,
                    incident_type="fairness_drift",
                    entity_type=entity_type,
                    drift_amount=drift,
                    baseline_recall=baseline_recall,
                    production_recall=production_recall,
                )

                alert = {
                    "entity_type": entity_type,
                    "drift": round(drift, 4),
                    "baseline_recall": round(baseline_recall, 4),
                    "production_recall": round(production_recall, 4),
                    "severity": sev.name,
                    "incident_id": incident_id,
                }
                alerts.append(alert)

                if emit_event is not None:
                    emit_event({
                        "event_type": "fairness_drift_detected",
                        "incident_id": incident_id,
                        "entity_type": entity_type,
                        "drift": round(drift, 4),
                        "baseline_recall": round(baseline_recall, 4),
                        "production_recall": round(production_recall, 4),
                        "severity": sev.name,
                        "timestamp": datetime.now(UTC).isoformat(),
                    })

        return alerts
