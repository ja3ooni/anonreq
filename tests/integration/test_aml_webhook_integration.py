"""AML webhook integration tests.

Covers:
- Webhook fires when confidence >= tenant threshold
- Webhook does NOT fire below threshold
- Webhook does NOT fire for unconfigured entity types
- Metadata-only payload (no raw entity values)
- HMAC-SHA256 signature on webhook requests
- Delivery failure is non-blocking (logged, pipeline unaffected)
- Tenant config can be set and retrieved
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from anonreq.governance.webhooks.aml import AmlWebhookManager
from anonreq.models.governance import AmlWebhookConfig

_TENANT_ID = "test-tenant"


@pytest.fixture
def manager() -> AmlWebhookManager:
    return AmlWebhookManager()


@pytest.fixture
def configured_manager() -> AmlWebhookManager:
    """Manager with a test tenant configured at 0.85 threshold."""
    m = AmlWebhookManager()
    # Set config in the in-memory store
    import anonreq.governance.webhooks.aml as aml_mod
    aml_mod._aml_config_store[_TENANT_ID] = AmlWebhookConfig(
        tenant_id=_TENANT_ID,
        webhook_url="https://aml.test.com/hook",
        secret="test-hmac-secret-12345",
        enabled=True,
        threshold=0.85,
        entity_types=["IBAN", "PAYMENT_REF", "CUSTOMER_ID", "AML_CASE_REF"],
    )
    return m


# ── Firing ────────────────────────────────────────────────────────


class TestWebhookFiring:
    """Verify webhook fires at correct threshold."""

    @pytest.mark.asyncio
    async def test_fires_at_threshold(self, configured_manager: AmlWebhookManager):
        """Webhook fires when confidence is at the threshold."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        configured_manager._http_client = mock_client

        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.85,
            session_metadata={"source": "test"},
        )
        assert result is True, "Webhook should fire at threshold"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_fires_above_threshold(self, configured_manager: AmlWebhookManager):
        """Webhook fires when confidence exceeds threshold."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        configured_manager._http_client = mock_client

        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        assert result is True, "Webhook should fire above threshold"

    @pytest.mark.asyncio
    async def test_does_not_fire_below_threshold(
        self, configured_manager: AmlWebhookManager
    ):
        """Webhook does NOT fire when confidence is below threshold."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        configured_manager._http_client = mock_client

        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.50,
            session_metadata={"source": "test"},
        )
        assert result is False, "Webhook should NOT fire below threshold"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_fire_for_unconfigured_type(
        self, configured_manager: AmlWebhookManager
    ):
        """Webhook does NOT fire for entity types not in configured list."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        configured_manager._http_client = mock_client

        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="PERSON",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        assert result is False, \
            "Webhook should NOT fire for unconfigured entity type"
        mock_client.post.assert_not_called()


# ── Payload structure ─────────────────────────────────────────────


class TestWebhookPayload:
    """Verify webhook payload is metadata-only."""

    @pytest.mark.asyncio
    async def test_payload_metadata_only_no_raw_pii(
        self, configured_manager: AmlWebhookManager
    ):
        """Webhook payload must not contain raw entity values."""
        captured_body = {}

        async def capture(_url, *, _headers=None, json=None, **_kwargs):
            captured_body.update(json or {})
            return MagicMock(spec=httpx.Response, status_code=200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = capture
        configured_manager._http_client = mock_client

        await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"session_id": "sess_abc123"},
        )
        body_str = json.dumps(captured_body)
        assert "DE89370400440532013000" not in body_str, \
            "Raw IBAN must not appear in webhook payload"
        assert "entity_type" in captured_body, \
            "Payload must include entity_type"

    @pytest.mark.asyncio
    async def test_hmac_signature_present(
        self, configured_manager: AmlWebhookManager
    ):
        """Webhook request has X-AML-Signature header."""
        captured_headers = {}

        async def capture(_url, *, headers=None, _json=None, **_kwargs):
            captured_headers.update(headers or {})
            return MagicMock(spec=httpx.Response, status_code=200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = capture
        configured_manager._http_client = mock_client

        await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        assert "X-AML-Signature" in captured_headers, \
            "X-AML-Signature header must be present"

    @pytest.mark.asyncio
    async def test_hmac_signature_verifiable(
        self, configured_manager: AmlWebhookManager
    ):
        """HMAC signature can be verified by the receiver."""
        captured_headers = {}
        captured_body = {}

        async def capture(_url, *, headers=None, json=None, **_kwargs):
            captured_headers.update(headers or {})
            captured_body.update(json or {})
            return MagicMock(spec=httpx.Response, status_code=200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = capture
        configured_manager._http_client = mock_client

        await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        sig = captured_headers.get("X-AML-Signature", "")
        body_str = json.dumps(captured_body, default=str)
        expected = hmac.new(
            b"test-hmac-secret-12345",
            body_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert sig == f"sha256={expected}", \
            "HMAC signature must be verifiable with the shared secret"


# ── Delivery failure ──────────────────────────────────────────────


class TestDeliveryFailure:
    """Verify delivery failures are non-blocking."""

    @pytest.mark.asyncio
    async def test_non_2xx_does_not_block(
        self, configured_manager: AmlWebhookManager
    ):
        """Non-2xx response is logged but pipeline continues."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Error"
        mock_client.post.return_value = mock_resp
        configured_manager._http_client = mock_client

        # Should not raise — pipeline continues
        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        # evaluate_and_fire returns True if it attempted to fire
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_does_not_block(
        self, configured_manager: AmlWebhookManager
    ):
        """Timeout during delivery does not raise."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        configured_manager._http_client = mock_client

        result = await configured_manager.evaluate_and_fire(
            tenant_id=_TENANT_ID,
            entity_type="IBAN",
            confidence=0.95,
            session_metadata={"source": "test"},
        )
        assert result is True, \
            "evaluate_and_fire should still return True (fire attempted)"


# ── Config management ─────────────────────────────────────────────


class TestWebhookConfig:
    """Verify tenant webhook config CRUD."""

    @pytest.mark.asyncio
    async def test_get_config(self, manager: AmlWebhookManager):
        """Getting a configured tenant returns their config."""
        cfg = await manager.get_config("acme-corp")
        assert cfg is not None
        assert cfg.tenant_id == "acme-corp"
        assert cfg.threshold == 0.85

    @pytest.mark.asyncio
    async def test_get_unknown_tenant(self, manager: AmlWebhookManager):
        """Getting config for unknown tenant returns None."""
        cfg = await manager.get_config("nonexistent")
        assert cfg is None

    @pytest.mark.asyncio
    async def test_set_and_get_config(self, manager: AmlWebhookManager):
        """Setting a config and retrieving returns consistent data."""
        cfg = AmlWebhookConfig(
            tenant_id="test-set",
            webhook_url="https://example.com/hook",
            secret="sec_12345",
            enabled=True,
            threshold=0.90,
            entity_types=["IBAN"],
        )
        saved = await manager.set_config("test-set", cfg)
        assert saved.tenant_id == "test-set"
        assert saved.threshold == 0.90

        retrieved = await manager.get_config("test-set")
        assert retrieved is not None
        assert retrieved.webhook_url == "https://example.com/hook"

        import anonreq.governance.webhooks.aml as aml_mod
        aml_mod._aml_config_store.pop("test-set", None)
