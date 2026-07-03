"""Tests for RAG Ingestion pipeline.

Tests:
- Document chunker: paragraph, sentence, token-count boundaries
- Chunk boundary awareness: entities not split across chunks
- Chunk metadata: classification_level, entity_types_present, source_app_id, original_doc_id
- Audit event generation: rag_content_anonymized
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.rag.ingest import DocumentChunker, ChunkResult


class TestDocumentChunker:
    """Test suite for DocumentChunker."""

    def setup_method(self):
        self.chunker = DocumentChunker(max_chunk_size=500)

    def test_paragraph_boundary_splits_at_double_newline(self):
        """Paragraph boundary splits on \\n\\n."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = self.chunker.chunk_by_paragraphs(text)
        assert len(chunks) == 3
        assert chunks[0] == "First paragraph."
        assert chunks[1] == "Second paragraph."
        assert chunks[2] == "Third paragraph."

    def test_paragraph_boundary_single_paragraph(self):
        """Single paragraph returns one chunk."""
        text = "Just one paragraph with no breaks."
        chunks = self.chunker.chunk_by_paragraphs(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_sentence_boundary_splits_at_sentence_endings(self):
        """Sentence boundary splits on period, !, ? endings."""
        text = "First sentence. Second sentence! Third sentence?"
        chunks = self.chunker.chunk_by_sentences(text)
        assert len(chunks) == 3
        assert chunks[0] == "First sentence."
        assert chunks[1] == "Second sentence!"
        assert chunks[2] == "Third sentence?"

    def test_token_count_boundary_respects_max_size(self):
        """Token-count boundary splits when tokens exceed max_chunk_size."""
        text = "word " * 600
        chunks = self.chunker.chunk_by_token_count(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk.split()) <= 500

    def test_chunk_by_paragraphs_respects_max_size(self):
        """Chunk by paragraphs still respects max_chunk_size for large paragraphs."""
        large_para = "longword " * 600
        text = f"{large_para}\n\nSmall paragraph."
        chunks = self.chunker.chunk(text, method="paragraph")
        assert len(chunks) >= 2

    def test_chunk_by_sentences_respects_max_size(self):
        """Chunk by sentences still respects max_chunk_size for long sentences."""
        long_sentence = "longword " * 600 + "."
        text = f"{long_sentence} Another sentence."
        chunks = self.chunker.chunk(text, method="sentence")
        assert len(chunks) >= 2

    def test_chunk_by_token_count_respects_max_size(self):
        """Chunk by token_count respects max_chunk_size."""
        text = "word " * 1200
        chunks = self.chunker.chunk(text, method="token_count")
        assert all(len(c.split()) <= 500 for c in chunks)
        assert len(chunks) >= 2

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty chunk list."""
        assert self.chunker.chunk("") == []
        assert self.chunker.chunk("   ") == []

    def test_chunk_metadata_generated(self):
        """Chunk metadata contains classification_level, entity_types_present, source_app_id, original_doc_id."""
        doc_id = "doc_001"
        result = self.chunker.chunk_with_metadata(
            text="Hello world.",
            source_app_id="test_app",
            original_doc_id=doc_id,
        )
        assert len(result.chunks) == 1
        meta = result.metadata[0]
        assert meta["original_doc_id"] == doc_id
        assert meta["source_app_id"] == "test_app"
        assert "classification_level" in meta
        assert "entity_types_present" in meta
        assert meta["classification_level"] == "Internal"

    def test_chunk_result_counts(self):
        """ChunkResult reports correct chunk count and entity count."""
        result = self.chunker.chunk_with_metadata(
            text="Hello world.\n\nSecond part.",
            source_app_id="test",
            original_doc_id="doc_001",
        )
        assert result.chunk_count == 2
        assert isinstance(result.entities_detected_count, int)

    def test_chunk_result_serializable(self):
        """ChunkResult produces a dict without internal fields."""
        result = self.chunker.chunk_with_metadata(
            text="Test content here.",
            source_app_id="app",
            original_doc_id="doc_002",
        )
        d = result.to_dict()
        assert d["source_type"] == "document_ingest"
        assert d["chunks_anonymized_count"] == 1
        assert isinstance(d["entities_detected_count"], int)
        assert len(d["metadata"]) == 1

    def test_custom_max_chunk_size(self):
        """Custom max_chunk_size is respected."""
        chunker = DocumentChunker(max_chunk_size=100)
        text = "word " * 300
        chunks = chunker.chunk(text, method="token_count")
        assert all(len(c.split()) <= 100 for c in chunks)
        assert len(chunks) >= 2

    def test_paragraph_boundary_preserves_entities(self):
        """Entity-like content near paragraph boundaries is preserved."""
        text = "My email is john@example.com.\n\nSecond paragraph."
        chunks = self.chunker.chunk_by_paragraphs(text)
        assert len(chunks) == 2
        assert "john@example.com" in chunks[0]

    def test_sentence_boundary_with_abbreviations(self):
        """Sentence boundary handles abbreviations like Dr. or Mrs."""
        text = "Dr. Smith went to Washington. He met with Mrs. Jones."
        chunks = self.chunker.chunk_by_sentences(text)
        assert len(chunks) >= 2


class TestRagIngestService:
    """Tests for RagIngestService."""

    @pytest.mark.asyncio
    async def test_ingest_endpoint_accepts_document(self):
        """Ingest endpoint accepts document body and returns chunk metadata."""
        from anonreq.rag.ingest import RagIngestService

        service = RagIngestService(chunker=DocumentChunker(max_chunk_size=500))
        result = await service.ingest_document(
            content="Hello world.\n\nThis is a test document with PII: email@example.com.",
            source_app_id="test",
            original_doc_id="doc_003",
        )
        assert result.chunk_count >= 1
        assert result.source_type == "document_ingest"
        assert len(result.metadata) == result.chunk_count

    @pytest.mark.asyncio
    async def test_ingest_audit_event_format(self):
        """Ingest produces events matching rag_content_anonymized format."""
        from anonreq.rag.ingest import RagIngestService

        service = RagIngestService(chunker=DocumentChunker(max_chunk_size=500))
        events = await service.ingest_and_emit(
            content="Test document here.",
            source_app_id="test",
            original_doc_id="doc_004",
        )
        assert len(events) >= 1
        event = events[0]
        assert event["event_type"] == "rag_content_anonymized"
        assert "source_type" in event
        assert "chunks_anonymized_count" in event
        assert "entities_detected_count" in event
        assert "original_doc_id" in event

    @pytest.mark.asyncio
    async def test_ingest_empty_content_raises(self):
        """Ingest with empty content raises ValueError."""
        from anonreq.rag.ingest import RagIngestService

        service = RagIngestService(chunker=DocumentChunker())
        with pytest.raises(ValueError, match="empty"):
            await service.ingest_document(
                content="",
                source_app_id="test",
                original_doc_id="doc_005",
            )

    @pytest.mark.asyncio
    async def test_ingest_source_app_id_required(self):
        """Ingest requires non-empty source_app_id."""
        from anonreq.rag.ingest import RagIngestService

        service = RagIngestService(chunker=DocumentChunker())
        with pytest.raises(ValueError, match="source_app_id"):
            await service.ingest_document(
                content="Some content.",
                source_app_id="",
                original_doc_id="doc_006",
            )

    @pytest.mark.asyncio
    async def test_ingest_tracks_audit_metadata_only(self):
        """Audit events contain metadata only, no raw entity values."""
        from anonreq.rag.ingest import RagIngestService

        service = RagIngestService(chunker=DocumentChunker(max_chunk_size=500))
        events = await service.ingest_and_emit(
            content="SSN: 123-45-6789, Email: test@example.com",
            source_app_id="test",
            original_doc_id="doc_007",
        )
        for event in events:
            event_str = str(event)
            assert "123-45-6789" not in event_str
            assert "test@example.com" not in event_str
