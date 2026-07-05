"""RAG package — Secure RAG ingestion and retrieval pipelines.

Provides document chunking, anonymization at ingestion time,
retrieval policy evaluation, and token restoration for RAG content.
"""

from anonreq.rag.ingest import DocumentChunker, ChunkResult, RagIngestService
from anonreq.rag.policy import (
    RetrievalPolicyEngine,
    ChunkContext,
    UserContext,
    PolicyRuleResult,
    PolicyEvaluationResult,
)
from anonreq.rag.retrieval import RetrievalService, RetrievalResult
from anonreq.rag.metadata import ChunkMetadata, generate_metadata
from anonreq.rag.vector_connector import (
    VectorStoreConnector,
    create_connector,
    ConfigurationError,
)
from anonreq.rag.audit import (
    emit_rag_ingestion_event,
    emit_rag_filtered_event,
    emit_rag_restoration_event,
)
from anonreq.rag.detection import retrieval_time_detect
from anonreq.rag.restoration import RAGRestorationService, TailBuffer

__all__ = [
    "DocumentChunker",
    "ChunkResult",
    "RagIngestService",
    "RetrievalPolicyEngine",
    "ChunkContext",
    "UserContext",
    "PolicyRuleResult",
    "PolicyEvaluationResult",
    "RetrievalService",
    "RetrievalResult",
    "ChunkMetadata",
    "generate_metadata",
    "VectorStoreConnector",
    "create_connector",
    "ConfigurationError",
    "emit_rag_ingestion_event",
    "emit_rag_filtered_event",
    "emit_rag_restoration_event",
    "retrieval_time_detect",
    "RAGRestorationService",
    "TailBuffer",
]
