"""Access logs are metadata only and do not use uvicorn's request line."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.logging_config import setup_logging
from anonreq.middleware.access_log import AccessLogMiddleware


@pytest.mark.asyncio
async def test_access_log_is_route_template_without_query_or_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging(level="INFO")
    app = FastAPI()

    @app.middleware("http")
    async def set_request_id(request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = "req_access_test"
        return await call_next(request)

    app.add_middleware(AccessLogMiddleware)

    @app.post("/v1/items/{item_id}")
    async def update_item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/items/ada.lovelace@example.com",
            params={"ssn": "219-09-9999"},
            json={"note": "secret body 4111111111111111"},
        )

    assert response.status_code == 200
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.strip()]
    access = [line for line in lines if line.get("event") == "http.access"]
    assert len(access) == 1
    entry = access[0]
    assert entry["method"] == "POST"
    assert entry["route"] == "/v1/items/{item_id}"
    assert entry["status_code"] == 200
    assert entry["request_id"] == "req_access_test"
    assert isinstance(entry["duration_ms"], int)
    rendered = json.dumps(entry)
    assert "ada.lovelace@example.com" not in rendered
    assert "219-09-9999" not in rendered
    assert "4111111111111111" not in rendered
    assert "ssn=" not in rendered
    assert "secret body" not in rendered
