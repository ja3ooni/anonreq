"""Tests for fairness evaluation pipeline.

Uses SQLite in-memory for DB, mock MinIO, and mock detection engine.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.models.fairness import (
    Base,
    FairnessDataset,
    DemographicResult,
    FairnessResult,
    FairnessEvaluation,
)
from anonreq.fairness.datasets import FairnessDatasetManager
from anonreq.fairness.evaluation import FairnessEvaluator, RECALL_DISPARITY_THRESHOLD


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with the fairness schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def mock_minio():
    """Create a mock MinIO client for dataset storage."""

    class MockMinio:
        def __init__(self):
            self._objects: dict[str, bytes] = {}

        async def bucket_exists(self, bucket: str) -> bool:
            return True

        async def make_bucket(self, bucket: str) -> None:
            pass

        async def put_object(self, bucket, object_path, data, length, content_type):
            self._objects[object_path] = data.read() if hasattr(data, 'read') else data

        async def get_object(self, bucket, object_path):
            class Response:
                def __init__(self, data):
                    self._data = data

                def read(self):
                    return self._data

            data = self._objects.get(object_path)
            if data is None:
                raise FileNotFoundError(f"Object {object_path} not found")
            return Response(data)

    return MockMinio()


@pytest.fixture
async def manager(engine, mock_minio):
    """Create a dataset manager with registered test datasets."""
    mgr = FairnessDatasetManager(engine, mock_minio)
    return mgr


def build_synthetic_dataset(
    groups: dict[str, int],
    entity_type: str = "PERSON",
    detection_hits: dict[str, list[int]] | None = None,
) -> bytes:
    """Build a synthetic fairness dataset as JSONL bytes.

    Args:
        groups: Map of demographic group to count of examples.
        entity_type: Entity type to mark in each example.
        detection_hits: Optional map of which examples per group
            should be detected (by index). If None, all are detected.

    Returns:
        JSONL bytes.
    """
    lines: list[str] = []
    for group, count in groups.items():
        for i in range(count):
            detected = True
            if detection_hits and group in detection_hits:
                detected = i in detection_hits[group]
            text = (
                f"Example {i} for {group} with {entity_type.lower()}: "
                f"{'john@example.com' if detected else 'no entity here'}"
            )
            if entity_type == "EMAIL":
                text = f"My email is user{i}_{group}@example.com"
            elif entity_type == "PHONE":
                text = f"Call me at +1-555-{i:04d}"
            elif entity_type == "ADDRESS":
                text = f"{100 + i} Main Street, Cityville"
            lines.append(json.dumps({
                "text": text,
                "demographic_group": group,
                "entity_type": entity_type,
                "expected": detected,
            }))
    return ("\n".join(lines)).encode("utf-8")


async def _register_synthetic_dataset(
    manager: FairnessDatasetManager,
    dataset_id: str,
    groups: dict[str, int],
    entity_type: str = "PERSON",
    locale: str = "en-US",
) -> tuple[FairnessDataset, bytes]:
    """Helper to register a synthetic dataset for tests."""
    content = build_synthetic_dataset(groups, entity_type=entity_type)
    ds = FairnessDataset(
        id=dataset_id,
        sha256="",
        owner="test",
        approved_by="test-compliance",
        approval_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
        framework="test-bias",
        version="1.0",
        locale=locale,
        entity_type=entity_type,
        total_examples=sum(groups.values()),
        group_sizes=groups,
    )
    registered = await manager.register_dataset(ds, content)
    return registered, content


class TestRecallDisparity:
    """Tests for recall disparity computation logic."""

    def test_zero_disparity_single_group(self):
        """Single group produces 0.0 disparity."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        results = [
            DemographicResult(group="male", total=100, detected=95),
        ]
        disparity = evaluator.compute_recall_disparity(results)
        assert disparity == 0.0

    def test_zero_disparity_all_equal(self):
        """All groups same recall → 0.0 disparity."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        results = [
            DemographicResult(group="male", total=100, detected=95),
            DemographicResult(group="female", total=100, detected=95),
        ]
        disparity = evaluator.compute_recall_disparity(results)
        assert disparity == 0.0

    def test_computes_correct_disparity(self):
        """Test 2: compute_recall_disparity returns max difference."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        results = [
            DemographicResult(group="male", total=100, detected=95),
            DemographicResult(group="female", total=100, detected=85),
            DemographicResult(group="non_binary", total=100, detected=90),
        ]
        disparity = evaluator.compute_recall_disparity(results)
        assert disparity == pytest.approx(0.10, rel=1e-6)  # 0.95 - 0.85

    def test_disparity_with_edge_values(self):
        """Disparity with perfect and zero recall."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        results = [
            DemographicResult(group="male", total=100, detected=100),
            DemographicResult(group="female", total=100, detected=0),
        ]
        disparity = evaluator.compute_recall_disparity(results)
        assert disparity == 1.0


class TestBuildGate:
    """Tests for CI/CD build gate logic."""

    def test_build_passes_when_all_within_threshold(self):
        """All disparities within threshold → build passes."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        evaluation = FairnessEvaluation(
            id="eval_gate_001",
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.95,
                    demographic_results=[],
                    max_disparity=0.03,
                    threshold=0.05,
                ),
            ],
        )
        assert evaluator.should_fail_build(evaluation) is False

    def test_build_fails_when_disparity_exceeds(self):
        """Disparity > threshold → build fails."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        evaluation = FairnessEvaluation(
            id="eval_gate_002",
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.80,
                    demographic_results=[],
                    max_disparity=0.20,
                    threshold=0.05,
                ),
            ],
        )
        assert evaluator.should_fail_build(evaluation) is True

    def test_build_fails_when_any_entity_exceeds(self):
        """One entity type exceeding threshold causes build failure."""
        evaluator = FairnessEvaluator.__new__(FairnessEvaluator)
        evaluator.threshold = RECALL_DISPARITY_THRESHOLD
        evaluation = FairnessEvaluation(
            id="eval_gate_003",
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.97,
                    demographic_results=[],
                    max_disparity=0.02,
                    threshold=0.05,
                ),
                FairnessResult(
                    entity_type="EMAIL",
                    overall_recall=0.75,
                    demographic_results=[],
                    max_disparity=0.15,
                    threshold=0.05,
                ),
            ],
        )
        assert evaluator.should_fail_build(evaluation) is True


class TestFairnessEvaluationFull:
    """Full integration tests for fairness evaluation."""

    async def test_evaluate_fairness_computes_recall(self, manager):
        """Test 1: evaluate_fairness loads dataset, runs detection, computes recall per group."""
        dataset_id = "eval_test_001"
        registered, content = await _register_synthetic_dataset(
            manager, dataset_id,
            groups={"male": 10, "female": 10},
            entity_type="EMAIL",
        )

        def mock_detect(text: str) -> list[dict]:
            if "@example.com" in text or "email" in text.lower():
                return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98}]
            return []

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        evaluation = await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect,
        )

        assert evaluation is not None
        assert len(evaluation.results) == 1
        email_result = evaluation.results[0]
        assert email_result.entity_type == "EMAIL"
        assert email_result.overall_recall > 0.5

    async def test_evaluated_recall_matches_expected(self, manager):
        """Overall recall computed correctly across all groups."""
        dataset_id = "eval_recall_001"
        registered, content = await _register_synthetic_dataset(
            manager, dataset_id,
            groups={"male": 100, "female": 100},
            entity_type="EMAIL",
        )

        def mock_detect(text: str) -> list[dict]:
            if "@example.com" in text:
                return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98}]
            return []

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        evaluation = await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect,
        )

        assert len(evaluation.results) == 1
        result = evaluation.results[0]
        assert result.overall_recall > 0.98
        assert len(result.demographic_results) == 2

    async def test_disparity_threshold_pass(self, manager):
        """Test 3: Disparity ≤ 0.05 → result.passed = True."""
        dataset_id = "eval_threshold_pass_001"
        registered, content = await _register_synthetic_dataset(
            manager, dataset_id,
            groups={"male": 100, "female": 100},
            entity_type="EMAIL",
        )

        def mock_detect_all(text: str) -> list[dict]:
            return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98}]

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        evaluation = await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect_all,
        )

        assert evaluation.overall_passed is True
        for result in evaluation.results:
            assert result.passed is True

    async def test_disparity_threshold_fail(self, manager):
        """Test 4: Disparity > 0.05 → result.passed = False."""
        dataset_id = "eval_threshold_fail_001"

        def mock_detect_biased(text: str) -> list[dict]:
            if "female" in text:
                return []
            if "@example.com" in text:
                return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98}]
            return []

        content = build_synthetic_dataset({"male": 100, "female": 100}, entity_type="EMAIL")
        ds = FairnessDataset(
            id=dataset_id,
            sha256="",
            owner="test",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
            framework="test-bias",
            version="1.0",
            locale="en-US",
            entity_type="EMAIL",
            total_examples=200,
        )
        await manager.register_dataset(ds, content)

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        evaluation = await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect_biased,
        )

        assert len(evaluation.results) > 0
        for result in evaluation.results:
            if result.max_disparity > 0.05:
                assert result.passed is False

    async def test_evaluation_emits_audit_event(self, manager):
        """Test 6: Evaluation emits fairness_evaluation_completed audit event."""
        dataset_id = "eval_audit_001"
        registered, content = await _register_synthetic_dataset(
            manager, dataset_id,
            groups={"male": 50, "female": 50},
            entity_type="EMAIL",
        )

        def mock_detect(text: str) -> list[dict]:
            return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98}]

        events: list[dict] = []

        def emit_event(event: dict) -> None:
            events.append(event)

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect,
            emit_event=emit_event,
        )

        assert len(events) == 1
        assert events[0]["event_type"] == "fairness_evaluation_completed"
        assert events[0]["dataset_id"] == dataset_id
        assert "evaluation_id" in events[0]

    async def test_multi_entity_type_evaluation(self, manager):
        """Evaluation handles multiple entity types."""
        dataset_id = "eval_multi_001"
        content_lines = []
        for entity_type in ["EMAIL", "PHONE"]:
            lines_data = [
                {"text": f"user{i}_{entity_type.lower()}@example.com", "demographic_group": "male", "entity_type": entity_type}
                for i in range(5)
            ] + [
                {"text": f"user{i}_{entity_type.lower()}@example.com", "demographic_group": "female", "entity_type": entity_type}
                for i in range(5)
            ]
            content_lines.extend(lines_data)

        content = json.dumps(content_lines).encode("utf-8") if len(content_lines) == 1 else "\n".join(json.dumps(l) for l in content_lines).encode("utf-8")

        content = "\n".join(json.dumps(l) for l in content_lines).encode("utf-8")

        ds = FairnessDataset(
            id=dataset_id,
            sha256="",
            owner="test",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
            framework="test-bias",
            version="1.0",
            locale="en-US",
            entity_type="PERSON",
            total_examples=len(content_lines),
        )
        await manager.register_dataset(ds, content)

        def mock_detect(text: str) -> list[dict]:
            results = []
            if "@" in text:
                results.append({"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.98})
            if "phone" in text.lower():
                results.append({"entity_type": "PHONE", "start": 0, "end": len(text), "score": 0.95})
            return results

        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        evaluation = await evaluator.evaluate_fairness(
            dataset_id=dataset_id,
            version="1.0",
            detect_fn=mock_detect,
        )

        assert len(evaluation.results) > 0
        entity_types = {r.entity_type for r in evaluation.results}
        assert "EMAIL" in entity_types

    async def test_evaluation_fails_without_detection(self, manager):
        """Evaluator raises error without detection mechanism."""
        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        with pytest.raises(ValueError, match="No detection mechanism"):
            await evaluator.evaluate_fairness(
                dataset_id="nonexistent",
                version="1.0",
            )

    async def test_evaluation_fails_for_missing_dataset(self, manager):
        """Evaluator raises error for missing dataset."""
        evaluator = FairnessEvaluator(
            detection_pipeline=None,
            dataset_manager=manager,
        )

        def mock_detect(text: str) -> list[dict]:
            return []

        with pytest.raises(FileNotFoundError):
            await evaluator.evaluate_fairness(
                dataset_id="nonexistent_dataset",
                version="1.0",
                detect_fn=mock_detect,
            )
