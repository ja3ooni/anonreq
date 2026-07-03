"""Fairness evaluation and monitoring for PII detection bias assessment.

Per D-001 through D-008:
- FairnessDatasetManager: dataset storage in MinIO by content hash
- FairnessEvaluator: recall disparity computation and CI/CD gate
- FairnessMonitor: runtime drift monitoring against baseline
"""

from anonreq.fairness.datasets import FairnessDatasetManager
from anonreq.fairness.evaluation import FairnessEvaluator, RECALL_DISPARITY_THRESHOLD
from anonreq.fairness.monitoring import FairnessMonitor

__all__ = [
    "FairnessDatasetManager",
    "FairnessEvaluator",
    "FairnessMonitor",
    "RECALL_DISPARITY_THRESHOLD",
]
