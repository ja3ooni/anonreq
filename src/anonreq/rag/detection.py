"""Retrieval-time detection and re-anonymization for RAG pipeline.

Provides:
- retrieval_time_detect: Runs Detection Engine on retrieved chunks
"""

from __future__ import annotations

from typing import Any


async def retrieval_time_detect(
    chunks: list[dict[str, Any]],
    existing_mappings: dict[str, str] | None = None,
    detection_engine: Any = None,
    tokenization_engine: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Run retrieval-time detection on chunk content.

    For each chunk:
    1. Run Detection Engine to find new entities.
    2. Check if entity already in existing_mappings (preserve token).
    3. If new entity: tokenize and add to mappings.
    4. Return updated chunks and the combined mapping.

    Args:
        chunks: List of chunk dicts with 'text' and 'chunk_id' keys.
        existing_mappings: Pre-existing token mappings (from ingestion).
        detection_engine: Detection engine with detect() method.
        tokenization_engine: Tokenization engine with tokenize() method.

    Returns:
        Tuple of (updated_chunks, updated_mappings).
    """
    existing_mappings = existing_mappings or {}
    updated_mappings = dict(existing_mappings)

    for chunk in chunks:
        text = chunk.get("text", "")
        if not text or detection_engine is None:
            continue

        # Run detection on chunk text
        detection_result = await detection_engine.detect(text)
        detected_entities = getattr(detection_result, "entities", [])

        # For each detected entity, check if already mapped or needs new token
        for entity in detected_entities:
            entity_text = getattr(entity, "text", "") or entity.get("text", "")
            entity_type = getattr(entity, "type", "") or entity.get("entity_type", "")

            if not entity_text:
                continue

            # Check if entity already has a mapping
            already_mapped = False
            for _token, value in updated_mappings.items():
                if value == entity_text:
                    already_mapped = True
                    break

            if not already_mapped and tokenization_engine is not None:
                # Create new token for this entity
                token = f"[{entity_type}_{len(updated_mappings)}]"
                updated_mappings[token] = entity_text

        # Store detection info on chunk
        chunk["entity_count"] = len(detected_entities)
        chunk["entity_types"] = list(set(
            getattr(e, "type", "") or e.get("entity_type", "")
            for e in detected_entities
        ))

    return chunks, updated_mappings
