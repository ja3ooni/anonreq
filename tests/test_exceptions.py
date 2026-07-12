"""Tests for the fail-secure global exception handler.

Tests verify:
- All exception types return safe error envelopes with no information leakage
- OpenAI-compatible error format with request_id
- Correct HTTP status codes per error type
- No stack traces, PII, or internal URLs in responses
"""


import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def exception_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers for testing."""
    from anonreq.exceptions import (
        AuthenticationError,
        DependencyUnavailableError,
        global_exception_handler,
        http_exception_handler,
    )

    app = FastAPI(title="TestApp", version="0.0.0")

    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.get("/raise-generic")
    async def raise_generic():
        raise RuntimeError("Something broke internally")

    @app.get("/raise-dependency")
    async def raise_dependency():
        raise DependencyUnavailableError(dependency="valkey")

    @app.get("/raise-auth")
    async def raise_auth():
        raise AuthenticationError()

    @app.get("/raise-not-found")
    async def raise_not_found():
        raise HTTPException(status_code=404, detail="Item not found")

    @app.get("/raise-unauthorized")
    async def raise_unauthorized():
        raise HTTPException(status_code=401, detail="Not authenticated")

    @app.get("/raise-422")
    async def raise_validation():
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            name: str = Field(min_length=1)

        TestModel()  # will raise ValidationError

    return app


@pytest.fixture
async def client(exception_app: FastAPI):
    transport = ASGITransport(app=exception_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestExceptionEnvelope:
    """Tests for the OpenAI-compatible error envelope format."""

    async def test_unhandled_exception_returns_500(self, client: AsyncClient):
        """Test 1: Unhandled Exception returns HTTP 500."""
        response = await client.get("/raise-generic")
        assert response.status_code == 500

    async def test_error_envelope_structure(self, client: AsyncClient):
        """Error response has OpenAI-compatible envelope with error key."""
        response = await client.get("/raise-generic")
        body = response.json()
        assert "error" in body
        assert "message" in body["error"]
        assert "type" in body["error"]
        assert "code" in body["error"]

    async def test_no_stack_trace_in_response(self, client: AsyncClient):
        """Test 2: Response body has no stack trace."""
        response = await client.get("/raise-generic")
        body_text = response.text
        assert "Traceback" not in body_text
        assert "File \"" not in body_text
        assert "line" not in body_text.lower() or "stack trace" not in body_text.lower()

    async def test_no_internal_urls_in_response(self, client: AsyncClient):
        """Test 2: No internal URLs in response."""
        response = await client.get("/raise-generic")
        body_text = response.text
        assert "localhost" not in body_text
        assert "127.0.0.1" not in body_text
        assert "redis://" not in body_text
        assert "http://" not in body_text

    async def test_generic_error_message_does_not_leak(self, client: AsyncClient):
        """Test 2: Generic error doesn't leak original exception message."""
        response = await client.get("/raise-generic")
        body = response.json()
        assert body["error"]["message"] != "Something broke internally"
        assert "internal" in body["error"]["message"].lower() or "error" in body["error"]["message"].lower()  # noqa: E501

    async def test_dependency_unavailable_returns_503(self, client: AsyncClient):
        """Test 3: DependencyUnavailableError returns 503."""
        response = await client.get("/raise-dependency")
        assert response.status_code == 503

    async def test_dependency_unavailable_envelope(self, client: AsyncClient):
        """Test 3: DependencyUnavailableError has correct type and code."""
        response = await client.get("/raise-dependency")
        body = response.json()
        assert body["error"]["type"] == "service_unavailable"
        assert body["error"]["code"] == "dependency_unavailable"

    async def test_dependency_message_includes_name(self, client: AsyncClient):
        """DependencyUnavailableError message includes the dependency name."""
        response = await client.get("/raise-dependency")
        body = response.json()
        assert "valkey" in body["error"]["message"].lower()

    async def test_http_exception_404(self, client: AsyncClient):
        """Test 4: HTTPException 404 returns 404 with generic envelope."""
        response = await client.get("/raise-not-found")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["code"] == "http_error"

    async def test_http_exception_401(self, client: AsyncClient):
        """Test 4: HTTPException 401 returns 401 with generic envelope."""
        response = await client.get("/raise-unauthorized")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["type"] == "http_error"

    async def test_request_id_in_error_envelope(self, client: AsyncClient):
        """Test 5: Error envelope includes request_id field."""
        response = await client.get("/raise-generic")
        body = response.json()
        assert "request_id" in body["error"]
        assert body["error"]["request_id"] is not None

    async def test_authentication_error_returns_401(self, client: AsyncClient):
        """AuthenticationError returns 401."""
        response = await client.get("/raise-auth")
        assert response.status_code == 401

    async def test_authentication_error_envelope(self, client: AsyncClient):
        """AuthenticationError has correct type and code."""
        response = await client.get("/raise-auth")
        body = response.json()
        assert body["error"]["type"] == "authentication_error"
        assert body["error"]["code"] == "invalid_api_key"

    async def test_422_validation_error(self, client: AsyncClient):
        """Pydantic ValidationError becomes 422 generic envelope."""
        response = await client.get("/raise-422")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["type"] == "internal_error"
        assert "request_id" in body["error"]
