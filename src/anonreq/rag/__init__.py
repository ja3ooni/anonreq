"""RAG package — Secure RAG ingestion and retrieval pipelines.

Provides document chunking, anonymization at ingestion time,
retrieval policy evaluation, and token restoration for RAG content.
"""

from anonreq.rag.audit import (
    emit_rag_filtered_event,
    emit_rag_ingestion_event,
    emit_rag_restoration_event,
)
from anonreq.rag.detection import retrieval_time_detect
from anonreq.rag.ingest import ChunkResult, DocumentChunker, RagIngestService
from anonreq.rag.metadata import ChunkMetadata, generate_metadata
from anonreq.rag.policy import (
    ChunkContext,
    PolicyEvaluationResult,
    PolicyRuleResult,
    RetrievalPolicyEngine,
    UserContext,
)
from anonreq.rag.restoration import RAGRestorationService, TailBuffer
from anonreq.rag.retrieval import RetrievalResult, RetrievalService
from anonreq.rag.vector_connector import (
    ConfigurationError,
    VectorStoreConnector,
    create_connector,
)

__all__ = [
    "ChunkContext",
    "ChunkMetadata",
    "ChunkResult",
    "ConfigurationError",
    "DocumentChunker",
    "PolicyEvaluationResult",
    "PolicyRuleResult",
    "RAGRestorationService",
    "RagIngestService",
    "RetrievalPolicyEngine",
    "RetrievalResult",
    "RetrievalService",
    "TailBuffer",
    "UserContext",
    "VectorStoreConnector",
    "create_connector",
    "emit_rag_filtered_event",
    "emit_rag_ingestion_event",
    "emit_rag_restoration_event",
    "generate_metadata",
    "retrieval_time_detect",
]
