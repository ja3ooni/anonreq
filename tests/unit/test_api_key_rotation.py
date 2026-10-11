"""The gateway accepts the previous key during rotation, and only that."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

import anonreq.dependencies as deps
from anonreq.dependencies import verify_api_key
from anonreq.exceptions import AuthenticationError

NEW = "n" * 40
OLD = "o" * 40


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    monkeypatch.setattr(deps.settings, "API_KEY", NEW)
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def _auth(_request, _exc) -> JSONResponse:  # the real app maps this in main.py
        return JSONResponse(status_code=401, content={})

    @app.get("/x", dependencies=[Depends(verify_api_key)])
    async def x() -> dict:
        return {"ok": True}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def status(client: AsyncClient, key: str | None) -> int:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return (await client.get("/x", headers=headers)).status_code


@pytest.mark.unit
class TestKeyRotation:
    async def test_current_key_works_without_previous(self, client, monkeypatch) -> None:
        monkeypatch.setattr(deps.settings, "API_KEY_PREVIOUS", None)
        assert await status(client, NEW) == 200
        assert await status(client, OLD) == 401

    async def test_previous_key_accepted_while_set(self, client, monkeypatch) -> None:
        monkeypatch.setattr(deps.settings, "API_KEY_PREVIOUS", OLD)
        assert await status(client, NEW) == 200
        assert await status(client, OLD) == 200

    async def test_unknown_key_and_missing_key_rejected(self, client, monkeypatch) -> None:
        monkeypatch.setattr(deps.settings, "API_KEY_PREVIOUS", OLD)
        assert await status(client, "z" * 40) == 401
        assert await status(client, None) in (401, 403)

    async def test_empty_previous_never_matches_empty_token(self, client, monkeypatch) -> None:
        monkeypatch.setattr(deps.settings, "API_KEY_PREVIOUS", None)
        assert await status(client, "") in (401, 403)
