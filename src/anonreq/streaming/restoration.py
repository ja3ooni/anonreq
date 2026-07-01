"""Streaming token restoration for assembled SSE text chunks."""

from __future__ import annotations

import re

from anonreq.cache.manager import CacheManager


class StreamingRestorationStage:
    """Restores token placeholders in streaming text chunks.

    The mapping is fetched once at stream start and kept in memory only for
    the lifetime of the stream. Matching is case-insensitive and accepts both
    bracketed tokens (``[EMAIL_1]``) and bare tokens (``EMAIL_1``).
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._cache = cache_manager
        self._mappings: dict[str, str] = {}
        self._lookup: dict[str, str] = {}

    async def start_session(self, tenant_id: str, session_id: str) -> None:
        self._mappings = await self._cache.get_mapping(tenant_id, session_id)
        self._lookup = {
            token.strip("[]").casefold(): value
            for token, value in self._mappings.items()
        }

    def restore_text(self, text: str) -> str:
        if not text or not self._lookup:
            return text

        token_cores = sorted(self._lookup.keys(), key=len, reverse=True)
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])\[?(" + "|".join(re.escape(t) for t in token_cores) + r")\]?(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )

        def replace(match: re.Match[str]) -> str:
            key = match.group(1).casefold()
            return self._lookup.get(key, match.group(0))

        return pattern.sub(replace, text)

    def close_session(self) -> None:
        self._mappings.clear()
        self._lookup.clear()
