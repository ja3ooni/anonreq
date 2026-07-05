"""RAG audit events and Prometheus metrics for ingestion and retrieval.

Provides:
- emit_rag_ingestion_event: Ingestion audit event
- emit_rag_filtered_event: Retrieval filtering audit event
- emit_rag_restoration_event: Token restoration audit event
- Prometheus counters for all RAG operations
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter

# Ingestion metrics
RAG_CHUNKS_INGESTED = Counter(
    "anonreq_rag_chunks_ingested_total",
    "Total number of RAG chunks ingested",
    ["source_type"],
)

RAG_ENTITIES_DETECTED = Counter(
    "anonreq_rag_entities_detected_total",
    "Total number of entities detected in RAG content",
    ["phase"],
)

# Retrieval metrics
RAG_CHUNKS_RETRIEVED = Counter(
    "anonreq_rag_chunks_retrieved_total",
    "Total number of chunks retrieved from vector store",
    ["source_type"],
)

RAG_CHUNKS_FILTERED = Counter(
    "anonreq_rag_chunks_filtered_total",
    "Total number of chunks filtered by retrieval policy",
    ["rule_id", "reason_code"],
)

RAG_POLICY_EVALUATIONS = Counter(
    "anonreq_rag_policy_evaluations_total",
    "Total policy evaluations by rule and result",
    ["rule_id", "result"],
)


def emit_rag_ingestion_event(
    audit_logger: Any,
    source_type: str,
    chunks_count: int,
    entities_count: int,
) -> dict[str, Any]:
    """Emit a rag_content_anonymized audit event.

    Args:
        audit_logger: Audit logger instance with log_event method.
        source_type: Source type identifier (e.g. document_ingest).
        chunks_count: Number of chunks ingested.
        entities_count: Number of entities detected.

    Returns:
        Event dict for testing/verification.
    """
    event: dict[str, Any] = {
        "event_type": "rag_content_anonymized",
        "source_type": source_type,
        "chunks_anonymized_count": chunks_count,
        "entities_detected_count": entities_count,
    }

    if audit_logger and hasattr(audit_logger, "log_event"):
        audit_logger.log_event(event)

    RAG_CHUNKS_INGESTED.labels(source_type=source_type).inc(chunks_count)
    RAG_ENTITIES_DETECTED.labels(phase="ingestion").inc(entities_count)

    return event


def emit_rag_filtered_event(
    audit_logger: Any,
    chunk_id: str,
    policy_rule_id: str,
    classification_level: str,
    reason_code: str = "policy_denied",
) -> dict[str, Any]:
    """Emit a rag_chunk_filtered audit event for a denied chunk.

    Args:
        audit_logger: Audit logger instance.
        chunk_id: ID of the filtered chunk.
        policy_rule_id: Rule ID that denied the chunk.
        classification_level: Classification level of the chunk.
        reason_code: Machine-readable reason code.

    Returns:
        Event dict.
    """
    event: dict[str, Any] = {
        "event_type": "rag_chunk_filtered",
        "chunk_id": chunk_id,
        "policy_rule_id": policy_rule_id,
        "classification_level": classification_level,
        "reason_code": reason_code,
    }

    if audit_logger and hasattr(audit_logger, "log_event"):
        audit_logger.log_event(event)

    RAG_CHUNKS_FILTERED.labels(
        rule_id=policy_rule_id,
        reason_code=reason_code,
    ).inc()

    return event


def emit_rag_restoration_event(
    audit_logger: Any,
    session_id: str,
    tokens_restored_count: int,
) -> dict[str, Any]:
    """Emit a rag_restoration_applied audit event.

    Args:
        audit_logger: Audit logger instance.
        session_id: Session ID for the restoration.
        tokens_restored_count: Number of tokens restored.

    Returns:
        Event dict.
    """
    event: dict[str, Any] = {
        "event_type": "rag_restoration_applied",
        "session_id": session_id,
        "tokens_restored_count": tokens_restored_count,
    }

    if audit_logger and hasattr(audit_logger, "log_event"):
        audit_logger.log_event(event)

    return event
