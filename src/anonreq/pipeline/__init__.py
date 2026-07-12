"""Pipeline orchestration package.

This package contains the pipeline stages and extraction logic for
the AnonReq anonymization pipeline.  Stages are sequential and
operate on a shared ``ProcessingContext`` per D-45 through D-49.
"""

from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.classification import ClassificationStage
from anonreq.pipeline.cleanup import CleanupStage
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.forwarding_guard import ForwardingGuard
from anonreq.pipeline.manager import PipelineManager
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.tokenization import TokenizationStage

__all__ = [
    "ClassificationStage",
    "CleanupStage",
    "DetectionStage",
    "ForwardingGuard",
    "PipelineManager",
    "PipelineStage",
    "ProviderStage",
    "RestorationStage",
    "TextExtractor",
    "TokenizationStage",
]
