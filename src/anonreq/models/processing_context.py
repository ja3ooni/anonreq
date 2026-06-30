"""ProcessingContext dataclass for pipeline stage state.

The ProcessingContext is the single shared state object that flows through
all pipeline stages. Each stage reads from and writes to the context as it
executes.  Per D-45 and D-46, stages are sequential — each stage populates
the fields it owns, and downstream stages read those fields.

Per D-49: any stage failure aborts the pipeline immediately by appending
to ``errors``. ``has_errors()`` checks before each stage executes.
``fail_secure()`` is the canonical way to record an error and trigger
pipeline abort.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessingContext:
    """State container for the anonymization pipeline.

    Created at the start of each request and populated by each pipeline
    stage as it executes.  Stages are sequential — the context carries
    request data, intermediate results, the final response, and any
    errors that occurred.

    Attributes:
        request_id: Unique identifier for this request (set at creation).
        tenant_id: Tenant identifier. Defaults to ``"default"``.
        context_id: UUIDv7 hex string used as the mapping-store key owner.
        original_request: Parsed ``ChatRequest`` as a dict, populated by
            the route handler before the pipeline starts.
        text_nodes: ``TextNode`` list from the extraction stage.
        classification_result: Result dict with ``action`` and
            ``matched_rule_ids`` keys.
        detections: List of detection result dicts with ``entity_type``,
            ``start``, ``end``, ``score``.
        token_mappings: Dict mapping ``"[TYPE_N]"`` tokens to original
            values.
        transformed_request: Sanitized request body after tokenization.
        provider_response: Raw response dict from the LLM provider.
        restored_response: Response dict with all tokens restored to
            original values.
        audit_metadata: Arbitrary metadata dict for audit log enrichment.
        errors: List of exceptions recorded during pipeline execution.
            Any non-empty list prevents downstream stage execution and
            ensures a fail-secure HTTP 5xx response.
    """

    request_id: str
    tenant_id: str = "default"
    context_id: str | None = None
    original_request: dict | None = None
    text_nodes: list[dict] | None = None
    classification_result: dict | None = None
    detections: list[dict] | None = None
    token_mappings: dict[str, str] | None = None
    transformed_request: dict | None = None
    provider_response: dict | None = None
    restored_response: dict | None = None
    audit_metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[Exception] = field(default_factory=list)

    def has_errors(self) -> bool:
        """Return True if any errors have been recorded."""
        return len(self.errors) > 0

    def fail_secure(self, error: Exception) -> None:
        """Record an error and signal pipeline abort per D-49.

        Any stage that encounters a non-recoverable error should call
        this method.  The pipeline manager checks ``has_errors()`` before
        invoking each subsequent stage and returns immediately if errors
        are present, ensuring no downstream stage — especially the
        provider call — ever executes.
        """
        self.errors.append(error)
