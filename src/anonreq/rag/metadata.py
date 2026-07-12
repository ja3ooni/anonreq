"""Chunk metadata schema and generator for RAG ingestion.

Provides:
- ChunkMetadata dataclass with all required fields
- generate_metadata factory function
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ChunkMetadata:
    """Metadata associated with a single chunk.

    Attributes:
        chunk_id: Unique chunk identifier (f"{original_doc_id}:{chunk_index}").
        original_doc_id: Identifier of the source document.
        source_app_id: Source application that created the chunk.
        classification_level: Data classification level.
        entity_types_present: Entity types detected in the chunk.
        entity_count: Total count of detected entities.
        token_count: Approximate token count.
        business_unit: Business unit that owns the data.
        created_at: Timestamp when the metadata was created.
    """

    chunk_id: str
    original_doc_id: str
    source_app_id: str
    classification_level: str = "Internal"
    entity_types_present: list[str] = field(default_factory=list)
    entity_count: int = 0
    token_count: int = 0
    business_unit: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata to dict (for storage/audit)."""
        return {
            "chunk_id": self.chunk_id,
            "original_doc_id": self.original_doc_id,
            "source_app_id": self.source_app_id,
            "classification_level": self.classification_level,
            "entity_types_present": list(self.entity_types_present),
            "entity_count": self.entity_count,
            "token_count": self.token_count,
            "business_unit": self.business_unit,
            "created_at": self.created_at.isoformat(),
        }


def generate_metadata(
    chunk_id: str,
    classification_level: str,
    entity_types: list[str],
    doc_metadata: dict[str, Any],
    token_count: int = 0,
) -> ChunkMetadata:
    """Factory function to create ChunkMetadata from component parts.

    Args:
        chunk_id: Unique chunk identifier.
        classification_level: Detected classification level.
        entity_types: Entity types present in the chunk.
        doc_metadata: Document-level metadata (source_app_id, original_doc_id, business_unit).
        token_count: Approximate token count for the chunk.

    Returns:
        ChunkMetadata instance.
    """
    return ChunkMetadata(
        chunk_id=chunk_id,
        original_doc_id=doc_metadata.get("original_doc_id", ""),
        source_app_id=doc_metadata.get("source_app_id", ""),
        classification_level=classification_level,
        entity_types_present=list(entity_types),
        entity_count=len(entity_types),
        token_count=token_count,
        business_unit=doc_metadata.get("business_unit"),
    )
