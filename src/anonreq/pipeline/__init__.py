"""Pipeline orchestration package.

This package contains the pipeline stages and extraction logic for
the AnonReq anonymization pipeline.  Stages are sequential and
operate on a shared ProcessingContext per D-45 through D-49.
"""

from anonreq.pipeline.extraction import TextExtractor

__all__ = [
    "TextExtractor",
]
