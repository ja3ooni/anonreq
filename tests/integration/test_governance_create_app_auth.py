"""create_app() governance auth: admin key, chat key, and tenant scope."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.main import create_app


@pytest.mark.asyncio
async def test_create_app_governance_admin_key_tenant_and_chat_key() -> None:
    """Admin key is scoped to the header tenant. The chat key is not admin."""
    app = create_app()
    slo = AsyncMock()
    slo.get_all_compliance.return_value = {}
    app.state.slo_engine = slo

    admin_headers = {
        "Authorization": f"Bearer {settings.ADMIN_API_KEY}",
        "X-AnonReq-Tenant-ID": "default",
    }
    chat_headers = {
        "Authorization": f"Bearer {settings.API_KEY}",
        "X-AnonReq-Tenant-ID": "default",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.get("/v1/governance/status", headers=admin_headers)
        assert allowed.status_code == 200
        assert allowed.json()["tenant_id"] == "default"

        chat_key = await client.get("/v1/governance/status", headers=chat_headers)
        assert chat_key.status_code == 403

        missing = await client.get(
            "/v1/governance/status",
            headers={"X-AnonReq-Tenant-ID": "default"},
        )
        assert missing.status_code == 401

        cross_tenant = await client.get(
            "/v1/governance/status?tenant_id=other-tenant",
            headers=admin_headers,
        )
        assert cross_tenant.status_code == 403
        assert slo.get_all_compliance.await_count == 1
        assert slo.get_all_compliance.await_args.args[0] == "default"
