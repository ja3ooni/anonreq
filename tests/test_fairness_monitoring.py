"""Tests for fairness drift monitoring.

Uses SQLite in-memory for metric storage and a mock incident classifier.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anonreq.fairness.monitoring import FairnessMonitor
from anonreq.models.fairness import (
    Base,
    DemographicResult,
    FairnessEvaluation,
    FairnessResult,
    ProductionMetricModel,
)


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with the fairness schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def make_baseline() -> FairnessEvaluation:
    """Create a baseline evaluation for drift comparison."""
    return FairnessEvaluation(
        id="baseline_001",
        version="1.0",
        evaluated_at=datetime(2026, 6, 20, tzinfo=UTC),
        results=[
            FairnessResult(
                entity_type="PERSON",
                overall_recall=0.95,
                demographic_results=[
                    DemographicResult(group="male", total=100, detected=95),
                    DemographicResult(group="female", total=100, detected=95),
                ],
                max_disparity=0.0,
                threshold=0.05,
                passed=True,
            ),
            FairnessResult(
                entity_type="EMAIL",
                overall_recall=0.92,
                demographic_results=[
                    DemographicResult(group="male", total=100, detected=92),
                    DemographicResult(group="female", total=100, detected=92),
                ],
                max_disparity=0.0,
                threshold=0.05,
                passed=True,
            ),
        ],
        overall_passed=True,
        dataset_id="ds_baseline_001",
    )


async def _insert_production_metrics(
    engine,
    entity_type: str,
    detected_count: int,
    total_count: int,
    demographic_group: str = "male",
    tenant_id: str = "tenant_001",
) -> None:
    """Insert production metrics for testing."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        for i in range(total_count):
            metric = ProductionMetricModel(
                tenant_id=tenant_id,
                entity_type=entity_type,
                demographic_group=demographic_group,
                detected=(i < detected_count),
                recorded_at=datetime.now(UTC),
            )
            session.add(metric)


class TestProductionMetricRecording:
    """Tests for recording production detection metrics."""

    async def test_record_production_metric_stores_entry(self, engine):
        """Test 3: record_production_metric stores per-session detection metrics."""
        monitor = FairnessMonitor(engine)

        await monitor.record_production_metric(
            tenant_id="tenant_001",
            entity_type="PERSON",
            detected=True,
            demographic_group="male",
        )

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            from sqlalchemy import func, select
            stmt = select(func.count(ProductionMetricModel.id))
            result = await session.execute(stmt)
            count = result.scalar_one()
            assert count == 1

    async def test_record_multiple_metrics(self, engine):
        """Multiple metrics recorded correctly."""
        monitor = FairnessMonitor(engine)

        for i in range(10):
            await monitor.record_production_metric(
                tenant_id="tenant_001",
                entity_type="PERSON",
                detected=(i % 2 == 0),
                demographic_group="female",
            )

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            from sqlalchemy import func, select
            stmt = select(func.count(ProductionMetricModel.id))
            result = await session.execute(stmt)
            assert result.scalar_one() == 10


class TestDriftDetection:
    """Tests for drift detection logic."""

    async def test_no_drift_when_production_matches_baseline(self, engine):
        """No drift alert when production matches baseline."""
        baseline = make_baseline()
        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
        )

        await _insert_production_metrics(
            engine, "PERSON", detected_count=95, total_count=100,
        )
        await _insert_production_metrics(
            engine, "EMAIL", detected_count=92, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        assert len(alerts) == 0

    async def test_drift_detected_when_production_decreases(self, engine):
        """Test 1: check_drift returns drift when production recall drops."""
        baseline = make_baseline()
        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
            drift_threshold=0.02,
        )

        await _insert_production_metrics(
            engine, "PERSON", detected_count=50, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        assert len(alerts) > 0
        assert alerts[0]["entity_type"] == "PERSON"
        assert alerts[0]["drift"] > 0.02

    async def test_drift_amount_matches_expected(self, engine):
        """Drift amount equals abs(baseline_recall - production_recall)."""
        baseline = make_baseline()
        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
            drift_threshold=0.01,
        )

        await _insert_production_metrics(
            engine, "PERSON", detected_count=80, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        assert len(alerts) > 0
        expected_drift = abs(0.95 - 0.80)
        assert abs(alerts[0]["drift"] - expected_drift) < 0.01

    async def test_drift_creates_incident(self, engine):
        """Test 2: Drift > threshold triggers alert and creates incident."""
        baseline = make_baseline()
        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
            drift_threshold=0.02,
        )

        await _insert_production_metrics(
            engine, "PERSON", detected_count=40, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        assert len(alerts) > 0
        assert "incident_id" in alerts[0]
        assert "severity" in alerts[0]
        assert alerts[0]["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    @pytest.mark.parametrize(("drift_threshold", "expected_alerts"), [
        (0.01, True),
        (0.50, False),
    ])
    async def test_drift_threshold_respected(self, engine, drift_threshold, expected_alerts):
        """Drift threshold correctly filters alerts."""
        baseline = make_baseline()
        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
            drift_threshold=drift_threshold,
        )

        await _insert_production_metrics(
            engine, "PERSON", detected_count=85, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        if expected_alerts:
            assert len(alerts) > 0
        else:
            assert len(alerts) == 0

    async def test_drift_emits_audit_event(self, engine):
        """Test 8: fairness_drift_detected audit event on drift trigger."""
        baseline = make_baseline()
        events: list[dict] = []

        def emit_event(event: dict) -> None:
            events.append(event)

        monitor = FairnessMonitor(
            engine,
            baseline_evaluation=baseline,
            drift_threshold=0.01,
        )

        await _insert_production_metrics(
            engine, "EMAIL", detected_count=50, total_count=100,
        )

        await monitor.check_drift(window_minutes=60, emit_event=emit_event)
        assert len(events) >= 1
        assert events[0]["event_type"] == "fairness_drift_detected"
        assert "drift" in events[0]
        assert "incident_id" in events[0]

    async def test_no_drift_without_baseline(self, engine):
        """check_drift returns empty when no baseline set."""
        monitor = FairnessMonitor(engine)

        alerts = await monitor.check_drift(window_minutes=60)
        assert alerts == []


class TestBaselineManagement:
    """Tests for baseline evaluation management."""

    async def test_set_baseline_updates_reference(self, engine):
        """set_baseline updates the baseline evaluation."""
        monitor = FairnessMonitor(engine)
        baseline = make_baseline()

        assert monitor._baseline is None
        await monitor.set_baseline(baseline)
        assert monitor._baseline is not None
        assert monitor._baseline.id == "baseline_001"

    async def test_drift_uses_updated_baseline(self, engine):
        """Drift monitor uses latest baseline after update."""
        monitor = FairnessMonitor(engine, drift_threshold=0.01)
        old_baseline = make_baseline()
        await monitor.set_baseline(old_baseline)

        new_baseline = FairnessEvaluation(
            id="baseline_002",
            version="2.0",
            evaluated_at=datetime(2026, 6, 21, tzinfo=UTC),
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.50,
                    demographic_results=[],
                    max_disparity=0.0,
                    threshold=0.05,
                    passed=True,
                ),
            ],
            overall_passed=True,
            dataset_id="ds_v2",
        )
        await monitor.set_baseline(new_baseline)

        await _insert_production_metrics(
            engine, "PERSON", detected_count=95, total_count=100,
        )

        alerts = await monitor.check_drift(window_minutes=60)
        assert len(alerts) > 0
        assert abs(alerts[0]["drift"] - 0.45) < 0.01
