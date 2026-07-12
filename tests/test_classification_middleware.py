"""Tests for ClassificationMiddleware — header parsing, blocking, response headers.

Plan 12-02:
- Parses X-AnonReq-Classification header
- Blocks HIGHLY_RESTRICTED with HTTP 451
- Stores client level on request.state for pipeline

Plan 12-03:
- X-AnonReq-Classification and X-AnonReq-Highest-Entity response headers
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import Response

from anonreq.models.classification import ClassificationLevel

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/"}


@pytest.fixture
def app():
    app = FastAPI()
    return app


@pytest.fixture
def classification_service_mock():
    svc = MagicMock()
    svc.parse_client_header = MagicMock(side_effect=lambda v: {
        "CONFIDENTIAL": ClassificationLevel.CONFIDENTIAL,
        "RESTRICTED": ClassificationLevel.RESTRICTED,
        "HIGHLY_RESTRICTED": ClassificationLevel.HIGHLY_RESTRICTED,
        "INTERNAL": ClassificationLevel.INTERNAL,
        "PUBLIC": ClassificationLevel.PUBLIC,
    }.get(v.upper() if v else ""))
    return svc


class TestClassificationMiddleware:
    """ClassificationMiddleware parses header and applies per-level handling."""

    @pytest.mark.asyncio
    async def test_skip_paths_no_header_processing(self, app):
        """Health and metrics paths are not processed."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_no_header_stores_none(self, app):
        """No classification header → request.state.client_classification is None."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(request: Request):
            assert request.state.client_classification is None
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/chat/completions")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_parses_client_header(self, app):
        """X-AnonReq-Classification header parsed and stored on state."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(request: Request):
            assert request.state.client_classification == ClassificationLevel.CONFIDENTIAL
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "CONFIDENTIAL"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_parses_client_header_lowercase(self, app):
        """Header value is case-insensitive."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(request: Request):
            assert request.state.client_classification == ClassificationLevel.RESTRICTED
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "restricted"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_blocks_highly_restricted_with_451(self, app):
        """HIGHLY_RESTRICTED client header → HTTP 451."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(_request: Request):
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "HIGHLY_RESTRICTED"},
            )
            assert response.status_code == 451
            body = response.json()
            assert "classification_block" in body.get("error", {}).get("type", "")

    @pytest.mark.asyncio
    async def test_highly_restricted_response_has_block_header(self, app):
        """Blocked response includes X-AnonReq-Classification and X-AnonReq-Blocked headers."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(_request: Request):
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "HIGHLY_RESTRICTED"},
            )
            assert response.headers.get("x-anonreq-classification") == "HIGHLY_RESTRICTED"
            assert response.headers.get("x-anonreq-blocked") == "true"

    @pytest.mark.asyncio
    async def test_confidential_passes_through(self, app):
        """CONFIDENTIAL or lower → request proceeds normally."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(request: Request):
            assert request.state.client_classification == ClassificationLevel.CONFIDENTIAL
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "CONFIDENTIAL"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_header_ignored(self, app):
        """Invalid classification header value → ignored (None stored)."""
        from anonreq.middleware.classification import ClassificationMiddleware

        app.add_middleware(ClassificationMiddleware)

        @app.get("/v1/chat/completions")
        async def chat(request: Request):
            assert request.state.client_classification is None
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/chat/completions",
                headers={"X-AnonReq-Classification": "INVALID_LEVEL"},
            )
            assert response.status_code == 200


class TestClassificationResponseHeaders:
    """Response headers for classification (Plan 12-03)."""

    @pytest.mark.asyncio
    async def test_response_includes_classification_and_highest_entity(self, app):
        """Route handler sets X-AnonReq-Classification and X-AnonReq-Highest-Entity."""
        from anonreq.services.classification import ClassificationService

        svc = ClassificationService()
        result = await svc.classify(
            ["PERSON", "EMAIL", "API_KEY"],
            client_level=None,
        )

        @app.get("/v1/chat/completions")
        async def chat(_request: Request, response: Response):
            response.headers["X-AnonReq-Classification"] = result.highest.name
            response.headers["X-AnonReq-Highest-Entity"] = result.highest_entity or ""
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/chat/completions")
            assert response.headers.get("x-anonreq-classification") == "HIGHLY_RESTRICTED"
            assert response.headers.get("x-anonreq-highest-entity") == "API_KEY"

    @pytest.mark.asyncio
    async def test_response_headers_with_internal(self, app):
        """INTERNAL classification produces correct response headers."""
        from anonreq.services.classification import ClassificationService

        svc = ClassificationService()
        result = await svc.classify(["PERSON"])

        @app.get("/v1/chat/completions")
        async def chat(_request: Request, response: Response):
            response.headers["X-AnonReq-Classification"] = result.highest.name
            response.headers["X-AnonReq-Highest-Entity"] = result.highest_entity or ""
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/chat/completions")
            assert response.headers.get("x-anonreq-classification") == "INTERNAL"
            assert response.headers.get("x-anonreq-highest-entity") == "PERSON"
