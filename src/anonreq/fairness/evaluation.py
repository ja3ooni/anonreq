"""Fairness evaluation pipeline with recall disparity computation.

Per D-001, D-002:
- Evaluates PII detection recall across demographic groups
- CI/CD gate blocks builds when disparity > 0.05
- Emits fairness_evaluation_completed audit event
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from anonreq.fairness.datasets import FairnessDatasetManager
from anonreq.models.fairness import (
    DemographicResult,
    FairnessEvaluation,
    FairnessResult,
)

logger = logging.getLogger("anonreq.fairness.evaluation")

RECALL_DISPARITY_THRESHOLD = 0.05


class FairnessEvaluator:
    """Evaluates PII detection fairness across demographic groups.

    Loads a fairness dataset, runs the detection pipeline on each example,
    computes recall per demographic group, and determines if disparity
    exceeds the threshold.
    """

    def __init__(
        self,
        detection_pipeline: Any | None = None,
        dataset_manager: FairnessDatasetManager | None = None,
        threshold: float = RECALL_DISPARITY_THRESHOLD,
    ) -> None:
        """Initialize the evaluator.

        Args:
            detection_pipeline: Object with an ``analyze(text)`` method
                returning list of detected entity dicts. If None, the
                evaluator uses a provided detect_fn at evaluation time.
            dataset_manager: FairnessDatasetManager for loading datasets.
            threshold: Maximum acceptable recall disparity (default 0.05).
        """
        self._detection_pipeline = detection_pipeline
        self._dataset_manager = dataset_manager
        self.threshold = threshold

    def compute_recall_disparity(
        self,
        results: list[DemographicResult],
    ) -> float:
        """Compute max recall disparity across demographic groups.

        disparity = max(recall) - min(recall) across all groups.

        Args:
            results: Demographic recall results for each group.

        Returns:
            The maximum recall disparity (0.0 if no results or single group).
        """
        if not results or len(results) < 2:
            return 0.0
        recalls = [r.recall for r in results]
        return max(recalls) - min(recalls)

    def should_fail_build(self, evaluation: FairnessEvaluation) -> bool:
        """Determine if the build should fail based on evaluation results.

        Build fails if any entity type's max_disparity > threshold.

        Args:
            evaluation: Completed FairnessEvaluation.

        Returns:
            True if any result exceeds the disparity threshold.
        """
        return any(r.max_disparity > self.threshold for r in evaluation.results)

    async def evaluate_fairness(
        self,
        dataset_id: str,
        version: str,
        git_sha: str | None = None,
        detect_fn: Callable[[str], list[dict[str, Any]]] | None = None,
        emit_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> FairnessEvaluation:
        """Run a complete fairness evaluation.

        Loads the dataset, runs detection on each example, computes
        recall per group and entity type, and returns the evaluation.

        Args:
            dataset_id: ID of the dataset to evaluate against.
            version: Version string for the evaluation.
            git_sha: Optional Git SHA for build traceability.
            detect_fn: Optional detection function override. If not
                provided, uses self._detection_pipeline.analyze().
            emit_event: Optional callback for audit event emission.

        Returns:
            FairnessEvaluation with per-entity-type results.

        Raises:
            ValueError: If no detection mechanism is configured.
            FileNotFoundError: If dataset not found.
        """
        if detect_fn is None and self._detection_pipeline is None:
            raise ValueError(
                "No detection mechanism available — provide detect_fn or "
                "configure detection_pipeline at construction"
            )

        actual_detect = detect_fn or (
            lambda text: self._detection_pipeline.analyze(text)
        )

        if self._dataset_manager is None:
            raise ValueError("No dataset_manager configured")

        dataset = await self._dataset_manager.get_dataset(dataset_id=dataset_id)
        if dataset is None:
            raise FileNotFoundError(f"Dataset not found: {dataset_id}")

        dataset_content = await self._dataset_manager.get_dataset_content(dataset.sha256)
        if not dataset_content:
            raise FileNotFoundError(f"Dataset content not found for {dataset_id}")

        lines = dataset_content.decode("utf-8").strip().split("\n")
        examples: list[dict[str, Any]] = []
        for line in lines:
            if line.strip():
                examples.append(json.loads(line))

        entity_type_results: dict[str, dict[str, dict[str, int]]] = {}
        demographic_set: set[str] = set()

        for example in examples:
            text = example.get("text", "")
            demo_group = example.get("demographic_group", "unknown")
            expected_entity = example.get("entity_type", dataset.entity_type)
            entity_type_str = expected_entity

            demographic_set.add(demo_group)

            if entity_type_str not in entity_type_results:
                entity_type_results[entity_type_str] = {}
            if demo_group not in entity_type_results[entity_type_str]:
                entity_type_results[entity_type_str][demo_group] = {"total": 0, "detected": 0}

            entity_type_results[entity_type_str][demo_group]["total"] += 1

            detections = actual_detect(text)
            found = any(
                d.get("entity_type") == entity_type_str
                for d in detections
            )
            if found:
                entity_type_results[entity_type_str][demo_group]["detected"] += 1

        results: list[FairnessResult] = []
        for entity_type_str, groups in entity_type_results.items():
            demo_results: list[DemographicResult] = []
            total_detected = 0
            total_examples = 0

            for group_name, counts in sorted(groups.items()):
                total = counts["total"]
                detected = counts["detected"]
                total_detected += detected
                total_examples += total
                demo_results.append(
                    DemographicResult(
                        group=group_name,
                        total=total,
                        detected=detected,
                    )
                )

            overall_recall = total_detected / total_examples if total_examples > 0 else 0.0
            max_disparity = self.compute_recall_disparity(demo_results)

            results.append(
                FairnessResult(
                    entity_type=entity_type_str,
                    overall_recall=overall_recall,
                    demographic_results=demo_results,
                    max_disparity=max_disparity,
                    threshold=self.threshold,
                )
            )

        evaluation = FairnessEvaluation(
            id=f"eval_{uuid4().hex[:16]}",
            version=version,
            results=results,
            dataset_id=dataset_id,
            git_sha=git_sha,
        )

        if emit_event is not None:
            emit_event({
                "event_type": "fairness_evaluation_completed",
                "evaluation_id": evaluation.id,
                "dataset_id": dataset_id,
                "version": version,
                "overall_passed": evaluation.overall_passed,
                "result_count": len(results),
                "timestamp": datetime.now(UTC).isoformat(),
            })

        return evaluation
