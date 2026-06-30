"""PresidioClient — async HTTP client for Presidio Analyzer sidecar.

Per D-32, D-34, D-37, D-50:
- One POST /analyze request per TextNode
- Per-TextNode concurrency via ``asyncio.gather()`` with semaphore (max 10)
- Short text nodes (< 20 characters) skip Presidio per D-34
- Default score threshold 0.7 per D-37
- Timeout: 2 seconds per D-50
- ``PresidioTimeoutError`` raised on timeout
- ``PresidioError`` raised on HTTP error
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


class PresidioTimeoutError(Exception):
    """Raised when Presidio Analyzer request times out per D-50."""


class PresidioError(Exception):
    """Raised when Presidio Analyzer returns a non-success HTTP status."""


class PresidioClient:
    """Async HTTP client for Presidio Analyzer sidecar.

    Usage::

        client = PresidioClient(base_url="http://presidio:5001")
        results = await client.analyze("John Smith")
        await client.close()
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        max_concurrency: int = 10,
    ) -> None:
        """Initialize the Presidio client.

        Args:
            base_url: Base URL of the Presidio Analyzer service
                (e.g. ``"http://presidio:5001"``).
            timeout: Request timeout in seconds (D-50 default: 2s).
            max_concurrency: Maximum concurrent requests (D-04, T-02-02-04).
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client: httpx.AsyncClient | None = None

    @property
    def _http_client(self) -> httpx.AsyncClient:
        """Lazy-initialized shared HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def analyze(
        self,
        text: str,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Send text to Presidio Analyzer for NER-based PII detection.

        Args:
            text: The text to analyze.
            language: Language code (default: ``"en"``).
            entities: Optional list of entity types to filter by.
                If ``None``, Presidio uses its default recognizer set.
            score_threshold: Minimum confidence score (default: 0.7, D-37).

        Returns:
            List of detection dicts with ``entity_type``, ``start``,
            ``end``, and ``score`` keys.

        Raises:
            PresidioTimeoutError: On request timeout (D-50).
            PresidioError: On non-success HTTP status.
        """
        body: dict[str, Any] = {
            "text": text,
            "language": language,
            "score_threshold": score_threshold,
        }
        if entities is not None:
            body["entities"] = entities

        async with self._semaphore:
            try:
                response = await self._http_client.post(
                    f"{self._base_url}/analyze",
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise PresidioTimeoutError(
                    f"Presidio request timed out after {self._timeout}s"
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise PresidioError(
                    f"Presidio returned HTTP {exc.response.status_code}"
                ) from exc

        # Normalize response fields
        results: list[dict[str, Any]] = []
        for item in data:
            results.append({
                "entity_type": item["entity_type"],
                "start": item["start"],
                "end": item["end"],
                "score": item["score"],
            })

        return results

    async def analyze_text_nodes(
        self,
        text_nodes: list[dict[str, str]],
        language: str = "en",
        score_threshold: float = 0.7,
    ) -> list[list[dict[str, Any]]]:
        """Analyze multiple text nodes concurrently.

        Per D-34: text nodes with fewer than 20 characters skip Presidio
        and return an empty list (regex only).

        Args:
            text_nodes: List of dicts with ``path``, ``role``, ``value``.
            language: Language code for all nodes.
            score_threshold: Minimum confidence score for all nodes.

        Returns:
            List of detection lists, one per text node (in the same order).
            Nodes that were skipped return an empty list.
        """
        if not text_nodes:
            return []

        async def _analyze_node(node: dict[str, str]) -> list[dict[str, Any]]:
            value = node.get("value", "")
            # D-34: Skip Presidio for short text nodes
            if len(value) < 20:
                return []
            return await self.analyze(
                text=value,
                language=language,
                score_threshold=score_threshold,
            )

        # Execute all analyze calls concurrently with semaphore control
        results = await asyncio.gather(
            *[_analyze_node(node) for node in text_nodes],
        )
        return list(results)

    async def health_check(self) -> dict[str, Any]:
        """Check Presidio Analyzer reachability.

        Returns:
            Dict with ``reachable`` (bool) and optional ``error`` key.
        """
        try:
            response = await self._http_client.get(f"{self._base_url}/health")
            response.raise_for_status()
            return {"reachable": True}
        except Exception as exc:
            return {"reachable": False, "error": str(exc)}

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
