"""RAG Retrieval pipeline — inspection, policy enforcement, and audit.

Provides:
- RetrievalService: intercepts retrieved chunks, applies policy, generates audit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from anonreq.rag.policy import (
    ChunkContext,
    RetrievalPolicyEngine,
    UserContext,
)

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of processing retrieved chunks.

    Attributes:
        allowed: Chunks that passed policy evaluation.
        denied: Chunks that were denied by policy.
        audit_events: Audit events for denied chunks.
    """

    allowed: list[ChunkContext] = field(default_factory=list)
    denied: list[ChunkContext] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)


class RetrievalService:
    """Intercepts retrieved chunks, applies policy rules, and generates audit log.

    Args:
        policy_engine: RetrievalPolicyEngine instance.
    """

    def __init__(self, policy_engine: RetrievalPolicyEngine) -> None:
        self._engine = policy_engine

    async def process_chunks(
        self,
        chunks: list[ChunkContext],
        user: UserContext,
    ) -> dict[str, Any]:
        """Process retrieved chunks through policy evaluation.

        Args:
            chunks: Retrieved chunks to evaluate.
            user: The requesting user context.

        Returns:
            Dict with "allowed", "denied", and "audit_events" keys.
        """
        allowed, denied = self._engine.filter_chunks(chunks, user)

        audit_events: list[dict[str, Any]] = []
        for chunk in denied:
            audit_events.append({
                "event_type": "rag_chunk_filtered",
                "chunk_id": chunk.chunk_id,
                "classification_level": chunk.classification_level,
                "tenant_id": "default",
            })

        return {
            "allowed": allowed,
            "denied": denied,
            "audit_events": audit_events,
        }
