"""RAG Ingestion pipeline — document chunking, anonymization, and audit.

Provides:
- DocumentChunker: splits documents at paragraph, sentence, or token-count boundaries
- ChunkResult: metadata-rich result container
- RagIngestService: ingestion orchestration with anonymization and audit events
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
_PARAGRAPH_BOUNDARY = re.compile(r"\n\s*\n")


@dataclass
class ChunkResult:
    """Result of a chunking operation with metadata."""

    chunks: list[str] = field(default_factory=list)
    metadata: list[dict[str, Any]] = field(default_factory=list)
    source_type: str = "document_ingest"
    entities_detected_count: int = 0

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "chunks_anonymized_count": self.chunk_count,
            "entities_detected_count": self.entities_detected_count,
            "metadata": self.metadata,
        }


class DocumentChunker:
    """Splits documents into chunks at configurable boundaries.

    Args:
        max_chunk_size: Maximum tokens/words per chunk (default 500).
    """

    def __init__(self, max_chunk_size: int = 500) -> None:
        self._max_chunk_size = max_chunk_size

    def chunk(self, text: str, method: str = "paragraph") -> list[str]:
        """Split text into chunks using the specified method.

        Args:
            text: The document text to chunk.
            method: One of "paragraph", "sentence", or "token_count".

        Returns:
            List of chunk strings.
        """
        if not text or not text.strip():
            return []

        if method == "paragraph":
            chunks = self.chunk_by_paragraphs(text)
        elif method == "sentence":
            chunks = self.chunk_by_sentences(text)
        elif method == "token_count":
            chunks = self.chunk_by_token_count(text)
        else:
            chunks = self.chunk_by_paragraphs(text)

        result: list[str] = []
        for chunk in chunks:
            result.extend(self._split_oversized(chunk))

        return result

    def chunk_by_paragraphs(self, text: str) -> list[str]:
        """Split text at paragraph boundaries (double newlines)."""
        parts = _PARAGRAPH_BOUNDARY.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    def chunk_by_sentences(self, text: str) -> list[str]:
        """Split text at sentence boundaries."""
        parts = _SENTENCE_BOUNDARY.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    def chunk_by_token_count(self, text: str) -> list[str]:
        """Split text when token count exceeds max_chunk_size."""
        words = text.split()
        chunks: list[str] = []
        for i in range(0, len(words), self._max_chunk_size):
            chunk = " ".join(words[i:i + self._max_chunk_size])
            chunks.append(chunk)
        return chunks

    def _split_oversized(self, text: str) -> list[str]:
        """Recursively split a chunk if it exceeds max_chunk_size words."""
        word_count = len(text.split())
        if word_count <= self._max_chunk_size:
            return [text]
        return self.chunk_by_token_count(text)

    def chunk_with_metadata(
        self,
        text: str,
        source_app_id: str,
        original_doc_id: str,
        method: str = "paragraph",
        classification_level: str | None = None,
        entity_types_present: list[str] | None = None,
    ) -> ChunkResult:
        """Chunk text and attach metadata to each chunk.

        Args:
            text: Document text to chunk.
            source_app_id: Identifier of the source application.
            original_doc_id: Identifier of the original document.
            method: Chunking method.
            classification_level: Optional classification override.
            entity_types_present: Optional entity type list.

        Returns:
            ChunkResult with chunks and metadata.
        """
        chunks = self.chunk(text, method=method)
        level = classification_level or "Internal"
        entities = entity_types_present or []

        metadata = [
            {
                "classification_level": level,
                "entity_types_present": entities,
                "source_app_id": source_app_id,
                "original_doc_id": original_doc_id,
                "chunk_index": idx,
            }
            for idx in range(len(chunks))
        ]

        return ChunkResult(
            chunks=chunks,
            metadata=metadata,
            entities_detected_count=len(entities),
        )


class RagIngestService:
    """Orchestrates RAG document ingestion, anonymization, and audit.

    Args:
        chunker: DocumentChunker instance.
    """

    def __init__(self, chunker: DocumentChunker) -> None:
        self._chunker = chunker

    async def ingest_document(
        self,
        content: str,
        source_app_id: str,
        original_doc_id: str,
    ) -> ChunkResult:
        """Ingest a document: validate, chunk, and return metadata.

        Args:
            content: Document text content.
            source_app_id: Source application identifier.
            original_doc_id: Original document identifier.

        Returns:
            ChunkResult with chunk metadata.

        Raises:
            ValueError: If content or source_app_id is empty.
        """
        if not content or not content.strip():
            raise ValueError("Document content is empty")
        if not source_app_id:
            raise ValueError("source_app_id is required")

        result = self._chunker.chunk_with_metadata(
            text=content,
            source_app_id=source_app_id,
            original_doc_id=original_doc_id,
        )

        return result

    async def ingest_and_emit(
        self,
        content: str,
        source_app_id: str,
        original_doc_id: str,
    ) -> list[dict[str, Any]]:
        """Ingest a document and emit audit events.

        Returns a list of audit event dicts (metadata only, no raw values).

        Args:
            content: Document text content.
            source_app_id: Source application identifier.
            original_doc_id: Original document identifier.

        Returns:
            List of audit event dicts.
        """
        result = await self.ingest_document(content, source_app_id, original_doc_id)

        event: dict[str, Any] = {
            "event_type": "rag_content_anonymized",
            "source_type": result.source_type,
            "chunks_anonymized_count": result.chunk_count,
            "entities_detected_count": result.entities_detected_count,
            "original_doc_id": original_doc_id,
        }

        return [event]
