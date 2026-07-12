"""RAG-specific token restoration in LLM responses.

Provides:
- RAGRestorationService: Restores tokenized content in LLM responses
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TailBuffer:
    """Buffer for handling split tokens in streaming responses.

    Accumulates partial content at the end of each chunk to handle
    cases where a token is split across two SSE chunks.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def process(self, chunk: str) -> str:
        """Process a streaming chunk, handling split tokens.

        Args:
            chunk: Incoming streaming chunk.

        Returns:
            Processed content with buffered tail merged.
        """
        combined = self._buffer + chunk
        # Reset buffer
        self._buffer = ""
        return combined

    def flush(self) -> str:
        """Flush any remaining buffered content.

        Returns:
            Remaining buffered content.
        """
        remaining = self._buffer
        self._buffer = ""
        return remaining


class RAGRestorationService:
    """Restores tokenized content in LLM responses.

    Reverses the tokenization applied during RAG ingestion/retrieval,
    replacing [TYPE_N] tokens with original values from session-scoped
    token mappings.

    Args:
        cache_manager: Cache manager for retrieving token mappings.
    """

    def __init__(self, cache_manager: Any = None) -> None:
        self._cache_manager = cache_manager

    async def restore_response(
        self,
        response: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        """Restore tokens in an LLM response dict.

        Deep-restores tokens in all string fields of the response.

        Args:
            response: LLM response dict.
            session_id: Session ID for token mapping lookup.

        Returns:
            Response with tokens restored.
        """
        mappings = await self._load_mappings(session_id)
        if not mappings:
            return response

        return self._restore_dict(response, mappings)

    async def restore_streaming(
        self,
        chunk: str,
        session_id: str,
        tail_buffer: TailBuffer,
    ) -> str:
        """Restore tokens in a streaming SSE chunk.

        Args:
            chunk: Streaming content chunk.
            session_id: Session ID for token mapping lookup.
            tail_buffer: TailBuffer for handling split tokens.

        Returns:
            Restored content.
        """
        mappings = await self._load_mappings(session_id)
        if not mappings:
            return chunk

        content = tail_buffer.process(chunk)
        return self._restore_text(content, mappings)

    async def _load_mappings(self, session_id: str) -> dict[str, str]:
        """Load token mappings for a session from cache."""
        if self._cache_manager is None:
            return {}

        try:
            cache_key = f"anonreq:rag:tokens:{session_id}"
            raw = await self._cache_manager.get(cache_key)
            if raw and isinstance(raw, dict):
                return raw
            return {}
        except Exception:
            logger.warning("Failed to load token mappings", exc_info=True)
            return {}

    def _restore_dict(
        self,
        d: dict[str, Any],
        mappings: dict[str, str],
    ) -> dict[str, Any]:
        """Recursively restore tokens in all string values of a dict."""
        result: dict[str, Any] = {}
        for key, value in d.items():
            if isinstance(value, str):
                result[key] = self._restore_text(value, mappings)
            elif isinstance(value, dict):
                result[key] = self._restore_dict(value, mappings)
            elif isinstance(value, list):
                result[key] = [
                    self._restore_text(item, mappings)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _restore_text(self, text: str, mappings: dict[str, str]) -> str:
        """Replace [TYPE_N] tokens with original values.

        Uses bracket-optional matching — both "[EMAIL_0]" and "EMAIL_0"
        forms are matched (without brackets matches inside surrounding text).

        Tokens are sorted by length descending to prevent partial matches
        (e.g., [EMAIL_10] matched before [EMAIL_1]).
        """
        if not text or not mappings:
            return text

        sorted_tokens = sorted(mappings.keys(), key=len, reverse=True)
        for token in sorted_tokens:
            original = mappings[token]
            # Replace both bracket and non-bracket forms
            text = text.replace(token, original)
            # Also try without brackets
            bare_token = token.strip("[]")
            text = text.replace(bare_token, original)

        return text
