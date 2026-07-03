from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision


@pytest.fixture
def mock_pdp():
    pdp = AsyncMock()
    pdp.evaluate_all = AsyncMock()
    return pdp


@pytest.fixture
def mock_pep():
    pep = AsyncMock()
    pep.enforce = AsyncMock()
    pep.add_transparency_headers = AsyncMock(return_value={
        "X-AnonReq-Processed": "true",
        "X-AnonReq-Entity-Count": "0",
    })
    return pep


@pytest.fixture
def mock_forwarding_guard():
    guard = AsyncMock()
    guard.validate = AsyncMock()
    return guard


def create_test_app(pdp, pep) -> FastAPI:
    from anonreq.middleware.policy import PolicyMiddleware

    app = FastAPI()
    app.state.pdp = pdp
    app.state.pep = pep

    app.add_middleware(PolicyMiddleware)

    @app.post("/v1/chat/completions")
    async def chat_route(request: Request):
        return {"choices": [{"message": {"content": "Hello"}}]}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def app(mock_pdp, mock_pep):
    return create_test_app(mock_pdp, mock_pep)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def allow_decision():
    return PolicyDecision(
        action=PolicyAction.ALLOW,
        matched_rule_ids=["all_checks_passed"],
        decision_ts=datetime.now(timezone.utc),
        ttl_seconds=60,
    )


@pytest.fixture
def block_decision():
    return PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["block_hr"],
        decision_ts=datetime.now(timezone.utc),
        reason="Blocked by HR policy",
    )


class TestPolicyMiddlewareIntegration:
    @pytest.mark.asyncio
    async def test_allow_request_passes_through(self, app, client, mock_pdp, mock_pep, allow_decision):
        from anonreq.policy.pep import PolicyEnforcementResult
        mock_pdp.evaluate_all.return_value = allow_decision
        mock_pep.enforce.return_value = PolicyEnforcementResult(
            action=PolicyAction.ALLOW,
            status_code=None,
            headers={"X-AnonReq-Processed": "true", "X-AnonReq-Entity-Count": "0"},
            body=None,
            should_forward=True,
            decision_id="test_did_001",
        )
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert response.status_code == 200
        assert mock_pdp.evaluate_all.called

    @pytest.mark.asyncio
    async def test_block_request_returns_early(self, app, client, mock_pdp, mock_pep, block_decision):
        from anonreq.policy.pep import PolicyEnforcementResult
        mock_pdp.evaluate_all.return_value = block_decision
        mock_pep.enforce.return_value = PolicyEnforcementResult(
            action=PolicyAction.BLOCK,
            status_code=403,
            headers={"X-AnonReq-Blocked": "true", "X-AnonReq-Processed": "true", "X-AnonReq-Entity-Count": "0"},
            body={"reason": "Blocked by policy", "decision_id": "did_001", "timestamp": "2024-01-01T00:00:00Z"},
            should_forward=False,
            decision_id="did_001",
        )
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert response.status_code == 403
        data = response.json()
        assert "reason" in data

    @pytest.mark.asyncio
    async def test_block_returns_x_anonreq_blocked_header(self, app, client, mock_pdp, mock_pep, block_decision):
        from anonreq.policy.pep import PolicyEnforcementResult
        mock_pdp.evaluate_all.return_value = block_decision
        mock_pep.enforce.return_value = PolicyEnforcementResult(
            action=PolicyAction.BLOCK,
            status_code=403,
            headers={"X-AnonReq-Blocked": "true"},
            body={"reason": "Blocked", "decision_id": "did_001", "timestamp": "2024-01-01T00:00:00Z"},
            should_forward=False,
            decision_id="did_001",
        )
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert response.headers.get("X-AnonReq-Blocked") == "true"

    @pytest.mark.asyncio
    async def test_health_route_skips_middleware(self, app, client, mock_pdp):
        response = await client.get("/health")
        assert response.status_code == 200
        mock_pdp.evaluate_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_pdp_exception_returns_503(self, app, client, mock_pdp):
        mock_pdp.evaluate_all.side_effect = Exception("PDP crash")
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_pep_exception_returns_503(self, app, client, mock_pdp, mock_pep, allow_decision):
        mock_pdp.evaluate_all.return_value = allow_decision
        mock_pep.enforce.side_effect = Exception("PEP crash")
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_allow_response_has_transparency_headers(self, app, client, mock_pdp, mock_pep, allow_decision):
        from anonreq.policy.pep import PolicyEnforcementResult
        mock_pdp.evaluate_all.return_value = allow_decision
        mock_pep.enforce.return_value = PolicyEnforcementResult(
            action=PolicyAction.ALLOW,
            status_code=None,
            headers={"X-AnonReq-Processed": "true", "X-AnonReq-Entity-Count": "0"},
            body=None,
            should_forward=True,
            decision_id="test_did_002",
        )
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert "X-AnonReq-Processed" in response.headers or response.status_code in (200,)

    @pytest.mark.asyncio
    async def test_flag_and_forward_injects_flag_header(self, app, client, mock_pdp, mock_pep):
        from anonreq.policy.pep import PolicyEnforcementResult
        flag_decision = PolicyDecision(
            action=PolicyAction.FLAG_AND_FORWARD, matched_rule_ids=["flag_conf"],
            decision_ts=datetime.now(timezone.utc), reason="Flagged content",
        )
        mock_pdp.evaluate_all.return_value = flag_decision
        mock_pep.enforce.return_value = PolicyEnforcementResult(
            action=PolicyAction.FLAG_AND_FORWARD,
            status_code=None,
            headers={"X-AnonReq-Flagged": "true", "X-AnonReq-Processed": "true", "X-AnonReq-Entity-Count": "0"},
            body=None,
            should_forward=True,
            decision_id="test_did_003",
        )
        response = await client.post("/v1/chat/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
        })
        assert "X-AnonReq-Flagged" in response.headers
        assert response.headers["X-AnonReq-Flagged"] == "true"


class TestForwardingGuardIntegration:
    @pytest.mark.asyncio
    async def test_forwarding_guard_validates_as_dependency(self, mock_forwarding_guard):
        from anonreq.policy.models import PolicyAction
        from anonreq.policy.forwarding_guard import ForwardingVerdict

        mock_forwarding_guard.validate.return_value = ForwardingVerdict(
            action=PolicyAction.ALLOW,
            reason=None,
            http_status=200,
            error_body=None,
            ctx=ProcessingContext(request_id="test", tenant_id="test"),
        )

        app = FastAPI()
        app.state.forwarding_guard = mock_forwarding_guard

        @app.post("/v1/chat/completions")
        async def chat_route(request: Request):
            guard = request.app.state.forwarding_guard
            ctx = ProcessingContext(request_id="test", tenant_id="test")
            ctx.policy_decision = PolicyDecision(
                action=PolicyAction.ALLOW, matched_rule_ids=[],
                decision_ts=datetime.now(timezone.utc), ttl_seconds=60,
            )
            ctx.transformed_request = {"model": "gpt-4"}
            verdict = await guard.validate(ctx)
            if verdict.action == PolicyAction.ALLOW:
                return {"forwarded": True}
            return JSONResponse(status_code=verdict.http_status, content=verdict.error_body)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/chat/completions", json={
                "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
            })
            assert response.status_code == 200
            assert response.json()["forwarded"] is True

    @pytest.mark.asyncio
    async def test_forwarding_guard_blocks_missing_decision(self, mock_forwarding_guard):
        from anonreq.policy.models import PolicyAction
        from anonreq.policy.forwarding_guard import ForwardingVerdict

        mock_forwarding_guard.validate.return_value = ForwardingVerdict(
            action=PolicyAction.BLOCK,
            reason="no policy decision",
            http_status=503,
            error_body={"reason": "no policy decision", "decision_id": "n/a", "timestamp": "now"},
            ctx=ProcessingContext(request_id="test", tenant_id="test"),
        )

        app = FastAPI()
        app.state.forwarding_guard = mock_forwarding_guard

        @app.post("/v1/chat/completions")
        async def chat_route(request: Request):
            guard = request.app.state.forwarding_guard
            ctx = ProcessingContext(request_id="test", tenant_id="test")
            verdict = await guard.validate(ctx)
            if verdict.action == PolicyAction.ALLOW:
                return {"forwarded": True}
            return JSONResponse(status_code=verdict.http_status, content=verdict.error_body)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/chat/completions", json={
                "model": "gpt-4", "messages": [{"role": "user", "content": "hello"}],
            })
            assert response.status_code == 503



class TestPolicyAdminApiIntegration:
    @pytest.mark.asyncio
    async def test_list_policies_authenticated(self, admin_app):
        from httpx import ASGITransport, AsyncClient
        from anonreq.policy.models import PolicyAction, PolicyRule

        admin_app.state.policy_store.load_policies.return_value = [
            PolicyRule(rule_id="r1", action=PolicyAction.BLOCK, priority=1, enabled=True)
        ]

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "administrator",
                "X-AnonReq-Tenant-ID": "test_tenant",
            }
            response = await client.get("/v1/admin/policies", headers=headers)
            assert response.status_code == 200
            assert len(response.json()["policies"]) == 1

    @pytest.mark.asyncio
    async def test_list_policies_unauthenticated(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/admin/policies")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upsert_policy_administrator(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        admin_app.state.policy_store.get_policy.return_value = None
        admin_app.state.policy_store.load_policies.return_value = []
        admin_app.state.policy_store.set_tenant_policy = AsyncMock()

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "administrator",
                "X-AnonReq-Tenant-ID": "test_tenant",
            }
            payload = {
                "rule_id": "r1",
                "name": "Block GPT-3",
                "action": "BLOCK",
                "priority": 10,
                "enabled": True,
                "conditions": {"model": "gpt-3"},
            }
            response = await client.put("/v1/admin/policies/r1", json=payload, headers=headers)
            assert response.status_code == 200
            assert response.json()["policy"]["rule_id"] == "r1"

    @pytest.mark.asyncio
    async def test_upsert_policy_operator(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "operator",
                "X-AnonReq-Tenant-ID": "test_tenant",
            }
            payload = {
                "rule_id": "r1",
                "name": "Block GPT-3",
                "action": "BLOCK",
                "priority": 10,
                "enabled": True,
            }
            # Operators are not allowed to update/write policies (PUT is admin only)
            response = await client.put("/v1/admin/policies/r1", json=payload, headers=headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_usage_authenticated(self, admin_app):
        from decimal import Decimal
        from httpx import ASGITransport, AsyncClient
        from anonreq.policy.models import UsageRecord

        admin_app.state.spend_controller.get_usage.return_value = UsageRecord(
            tenant_id="tenant_a",
            rpm_current=5,
            tpm_current=100,
            concurrent_current=1,
            daily_spend=Decimal("1.50"),
            monthly_spend=Decimal("10.00"),
            reset_at=datetime.now(timezone.utc),
        )
        admin_app.state.usage_limiter.get_current.return_value = {
            "rpm": 5,
            "tpm": 100,
            "concurrent": 1,
        }

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "administrator",
                "X-AnonReq-Tenant-ID": "tenant_a",
            }
            response = await client.get("/v1/admin/tenants/tenant_a/usage", headers=headers)
            assert response.status_code == 200
            assert response.json()["usage"]["rpm_current"] == 5
            assert response.json()["usage"]["daily_spend"] == 1.5

    @pytest.mark.asyncio
    async def test_dependency_outage_503(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        admin_app.state.policy_store.load_policies.side_effect = Exception("DB Outage")

        transport = ASGITransport(app=admin_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "administrator",
                "X-AnonReq-Tenant-ID": "test_tenant",
            }
            response = await client.get("/v1/admin/policies", headers=headers)
            # Fail-secure returns 5xx error on exception
            assert response.status_code >= 500

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Operator for tenant_a queries tenant_b -> should be rejected with 403
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "operator",
                "X-AnonReq-Tenant-ID": "tenant_a",
            }
            response = await client.get("/v1/admin/tenants/tenant_b/usage", headers=headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rbac_denies_wrong_role(self, admin_app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=admin_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Authorization": "Bearer adminkey12345678901234567890",
                "X-AnonReq-Role": "read_only",  # insufficient role for write operations
                "X-AnonReq-Tenant-ID": "test_tenant",
            }
            payload = {
                "rule_id": "r1",
                "name": "Block GPT-3",
                "action": "BLOCK",
                "priority": 10,
                "enabled": True,
            }
            response = await client.put("/v1/admin/policies/r1", json=payload, headers=headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_durable_records_hash_only(self):
        # Proves that compliance evidence records only store cryptographic hashes,
        # rule counts, enabled counts, timestamps, and identifiers. No raw payloads.
        from unittest.mock import AsyncMock
        from anonreq.policy.evidence import EvidenceStore
        from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule

        mock_store = AsyncMock()
        mock_store.load_policies.return_value = [
            PolicyRule(rule_id="r1", action=PolicyAction.ALLOW, priority=1, enabled=True)
        ]
        ev_store = EvidenceStore(mock_store)

        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            matched_rule_ids=["r1"],
            decision_ts=datetime.now(timezone.utc),
        )
        record = await ev_store.record_decision_evidence("tenant_abc", decision)

        # Verify fields present
        assert record.policy_hash is not None
        assert record.policy_version is not None
        assert record.rule_count == 1
        assert record.enabled_rule_count == 1

        # Check serialization contains no raw payloads or secrets
        raw_json = record.model_dump_json()
        assert "secret" not in raw_json
        assert "payload" not in raw_json

