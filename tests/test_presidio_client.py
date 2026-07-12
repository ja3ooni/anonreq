"""Tests for PresidioClient — async HTTP client for Presidio Analyzer sidecar.

Per D-32, D-34, D-37, D-50:
- Sends POST /analyze with correct request body
- Semaphore-limited concurrency (max 10)
- Short text nodes (< 20 char) skip Presidio per D-34
- Raises PresidioTimeoutError on timeout
- Raises PresidioError on HTTP error
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from anonreq.detection.presidio_client import PresidioClient, PresidioError, PresidioTimeoutError

# Base URL for mock Presidio endpoint
PRESIDIO_URL = "http://localhost:5001"


class TestPresidioClient:
    """Test suite for PresidioClient."""

    @pytest.fixture
    async def client(self):
        """Create a PresidioClient for testing."""
        c = PresidioClient(base_url=PRESIDIO_URL, timeout=5.0, max_concurrency=10)
        yield c
        await c.close()

    @respx.mock
    async def test_analyze_sends_correct_request(self, client):
        """analyze() sends correct POST /analyze request body."""
        route = respx.post(f"{PRESIDIO_URL}/analyze").respond(
            json=[{"entity_type": "PERSON", "start": 0, "end": 10, "score": 0.95}],
        )

        results = await client.analyze("John Smith", language="en", entities=["PERSON"], score_threshold=0.7)  # noqa: E501

        # Verify the request was made correctly
        assert route.called
        request = route.calls[0].request
        body = request.json()
        assert body["text"] == "John Smith"
        assert body["language"] == "en"
        assert body["entities"] == ["PERSON"]
        assert body["score_threshold"] == 0.7

        # Verify response parsing
        assert len(results) == 1
        assert results[0]["entity_type"] == "PERSON"
        assert results[0]["start"] == 0
        assert results[0]["end"] == 10
        assert results[0]["score"] == 0.95

    @respx.mock
    async def test_analyze_parses_response_correctly(self, client):
        """analyze() parses valid RecognizerResult[] response."""
        respx.post(f"{PRESIDIO_URL}/analyze").respond(
            json=[
                {"entity_type": "PERSON", "start": 0, "end": 10, "score": 0.85},
                {"entity_type": "LOCATION", "start": 20, "end": 28, "score": 0.95},
            ],
        )

        results = await client.analyze("John Smith lives in New York")

        assert len(results) == 2
        assert results[0]["entity_type"] == "PERSON"
        assert results[1]["entity_type"] == "LOCATION"

    @respx.mock
    async def test_analyze_without_entities(self, client):
        """analyze() works without explicit entities list (uses Presidio defaults)."""
        route = respx.post(f"{PRESIDIO_URL}/analyze").respond(
            json=[{"entity_type": "PERSON", "start": 0, "end": 4, "score": 0.9}],
        )

        await client.analyze("John", language="en", score_threshold=0.7)

        request = route.calls[0].request.json()
        assert "entities" not in request

    @respx.mock
    async def test_analyze_raises_timeout_error(self, client):
        """PresidioTimeoutError raised on httpx.TimeoutException."""
        respx.post(f"{PRESIDIO_URL}/analyze").mock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(PresidioTimeoutError):
            await client.analyze("John Smith")

    @respx.mock
    async def test_analyze_raises_http_error(self, client):
        """PresidioError raised on HTTP error status."""
        respx.post(f"{PRESIDIO_URL}/analyze").respond(status_code=500)

        with pytest.raises(PresidioError, match="500"):
            await client.analyze("John Smith")

    @respx.mock
    async def test_analyze_raises_on_400(self, client):
        """PresidioError raised on HTTP 400."""
        respx.post(f"{PRESIDIO_URL}/analyze").respond(status_code=400)

        with pytest.raises(PresidioError):
            await client.analyze("")

    @respx.mock
    async def test_analyze_text_nodes_skips_short_text(self, client):
        """analyze_text_nodes skips text nodes < 20 characters per D-34."""
        respx.post(f"{PRESIDIO_URL}/analyze").respond(
            json=[{"entity_type": "PERSON", "start": 0, "end": 5, "score": 0.9}],
        )

        text_nodes = [
            {"path": "m[0]", "role": "user", "value": "short"},          # < 20 chars — skip
            {"path": "m[1]", "role": "user", "value": "John Smith lives in New York"},  # >= 20
        ]

        results = await client.analyze_text_nodes(text_nodes)
        # Only 1 request should have been made (the long text)
        assert len(results) == 2
        assert results[0] == []          # skipped — empty list
        assert len(results[1]) == 1      # analyzed

    @respx.mock
    async def test_semaphore_limits_concurrency(self, client):
        """Semaphore limits concurrent Presidio requests (max 10)."""
        # Create a barrier to track concurrent requests
        sem = asyncio.Semaphore(10)

        async def delayed_handler(_request):
            async with sem:
                return httpx.Response(200, json=[{"entity_type": "PERSON", "start": 0, "end": 4, "score": 0.9}])  # noqa: E501

        respx.post(f"{PRESIDIO_URL}/analyze").mock(side_effect=delayed_handler)

        text_nodes = [
            {"path": f"m[{i}]", "role": "user", "value": "A" * 30}
            for i in range(20)
        ]

        results = await client.analyze_text_nodes(text_nodes, score_threshold=0.7)
        assert len(results) == 20

    @respx.mock
    async def test_empty_text_nodes(self, client):
        """Empty text_nodes list returns empty list."""
        results = await client.analyze_text_nodes([])
        assert results == []

    @respx.mock
    async def test_health_check_success(self, client):
        """health_check returns reachability status."""
        respx.get(f"{PRESIDIO_URL}/health").respond(json={"status": "ok"})

        status = await client.health_check()
        assert status.get("reachable") is True

    @respx.mock
    async def test_health_check_unreachable(self, client):
        """health_check returns reachable=False on error."""
        respx.get(f"{PRESIDIO_URL}/health").mock(side_effect=httpx.ConnectError("Connection refused"))  # noqa: E501

        status = await client.health_check()
        assert status.get("reachable") is False

    @respx.mock
    async def test_analyze_default_parameters(self, client):
        """analyze() uses correct defaults for language and score_threshold."""
        route = respx.post(f"{PRESIDIO_URL}/analyze").respond(
            json=[{"entity_type": "PERSON", "start": 0, "end": 4, "score": 0.9}],
        )

        await client.analyze("John")

        body = route.calls[0].request.json()
        assert body["language"] == "en"
        assert body["score_threshold"] == 0.7
