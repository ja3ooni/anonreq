"""API errors do not echo exception messages."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from anonreq.admin.provider_routes import router as provider_router
from anonreq.appliance.agent import ApplianceAgent
from anonreq.exceptions import http_exception_handler
from anonreq.middleware.rbac import Role

SENTINEL = "do-not-return-sentinel /var/lib/secret-volume"


def _provider_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def set_request_id(request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = "req_admin_test"
        request.state.role_principal = {
            "principal_id": "admin",
            "role": Role.ADMINISTRATOR,
            "tenant_id": "*",
        }
        return await call_next(request)

    app.include_router(provider_router)
    inventory = AsyncMock()
    inventory.suspend_provider.side_effect = ValueError(SENTINEL)
    app.state.provider_inventory = inventory
    return app


def test_admin_provider_error_is_generic_and_has_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(_provider_app())
    response = client.post(
        "/providers/prov-1/suspend",
        json={"reason": "test", "suspended_by": "admin"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["message"] == "Provider not found"
    assert body["error"]["request_id"] == "req_admin_test"
    assert SENTINEL not in response.text
    assert "ValueError" in caplog.text
    assert SENTINEL not in caplog.text


@pytest.mark.asyncio
async def test_appliance_disk_and_config_errors_omit_exception_text(
    caplog: pytest.LogCaptureFixture,
    tmp_path,
) -> None:
    agent = ApplianceAgent(config_path=str(tmp_path))

    with patch("anonreq.appliance.agent.shutil.disk_usage", side_effect=OSError(SENTINEL)):
        health = json.dumps(agent._get_disk_usage())
    assert SENTINEL not in health
    disk = json.loads(health)
    assert disk["error"]["message"] == "Unable to read disk usage"
    assert disk["error"]["request_id"].startswith("req_")
    assert "OSError" in caplog.text

    caplog.clear()
    real_open = open

    def raising_open(path, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
        if "w" in str(mode):
            raise OSError(SENTINEL)
        return real_open(path, mode, *args, **kwargs)

    with patch("builtins.open", raising_open):
        result = json.dumps(await agent.update_config({"data_dir": "/tmp/anonreq-data"}))
    assert SENTINEL not in result
    body = json.loads(result)
    assert body["error"]["code"] == "config_write_failed"
    assert body["error"]["request_id"].startswith("req_")
    assert "OSError" in caplog.text
    assert SENTINEL not in caplog.text

    caplog.clear()
    with patch(
        "anonreq.appliance.agent.asyncio.create_subprocess_shell",
        side_effect=OSError(SENTINEL),
    ):
        compose = await agent._run_compose_command("ps")
    rendered = json.dumps(compose)
    assert SENTINEL not in rendered
    assert compose["stderr"] == "Command failed"
    assert "OSError" in caplog.text
    assert SENTINEL not in caplog.text
