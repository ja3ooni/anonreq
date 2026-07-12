"""Tests for AML webhook (D-014).

Covers:
- Webhook fires when entity confidence exceeds tenant threshold
- Webhook does not fire when confidence below threshold
- Threshold configurable per tenant
- Webhook payload is metadata-only (no raw entity values)
- aml_webhook_fired audit event emitted
- Webhook delivery failure logged but non-blocking
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from anonreq.models.governance import AmlEventPayload, AmlWebhookConfig

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_config() -> AmlWebhookConfig:
    """Standard AML webhook config for tests."""
    return AmlWebhookConfig(
        tenant_id="acme-corp",
        webhook_url="https://hooks.acme-corp.com/aml/alert",
        secret="whsec_test_secret_key_12345",
        enabled=True,
        threshold=0.85,
        entity_types=["IBAN", "PAYMENT_REF", "CUSTOMER_ID", "AML_CASE_REF"],
    )


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock async DB session."""
    return AsyncMock()


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Mock httpx.AsyncClient."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock()
    client.post.return_value = MagicMock(status_code=200)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_audit_emitter() -> MagicMock:
    """Mock audit event emitter."""
    return MagicMock()


# ── AmlWebhookConfig tests ─────────────────────────────────────────────────


class TestAmlWebhookConfig:
    """AmlWebhookConfig model validation."""

    def test_minimal_config(self):
        """Config with only required fields."""
        config = AmlWebhookConfig(
            tenant_id="test-tenant",
            webhook_url="https://example.com/webhook",
        )
        assert config.tenant_id == "test-tenant"
        assert config.webhook_url == "https://example.com/webhook"
        assert config.enabled is True
        assert config.threshold == 0.85
        assert config.entity_types is None

    def test_full_config(self, sample_config: AmlWebhookConfig):
        """Config with all fields populated."""
        assert sample_config.threshold == 0.85
        assert sample_config.enabled is True
        assert "IBAN" in sample_config.entity_types

    def test_threshold_validation(self):
        """Threshold must be between 0.0 and 1.0."""
        # Value 0.5 is valid
        config = AmlWebhookConfig(
            tenant_id="t", webhook_url="https://example.com/w", threshold=0.5,
        )
        assert config.threshold == 0.5

        # Value 1.0 is valid
        config = AmlWebhookConfig(
            tenant_id="t", webhook_url="https://example.com/w", threshold=1.0,
        )
        assert config.threshold == 1.0


# ── AmlEventPayload tests ──────────────────────────────────────────────────


class TestAmlEventPayload:
    """AmlEventPayload model validation."""

    def test_payload_creation(self):
        """Create a valid payload."""
        datetime.now(UTC)
        payload = AmlEventPayload(
            event_id=str(uuid.uuid4()),
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence_score=0.92,
            threshold=0.85,
            session_metadata={"session_id": "sess_123"},
        )
        assert payload.event_type == "aml_alert"
        assert payload.confidence_score == 0.92
        assert payload.alert_id is not None

    def test_no_raw_entity_values(self):
        """Payload model_dump must not contain raw entity values."""
        payload = AmlEventPayload(
            event_id=str(uuid.uuid4()),
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence_score=0.92,
            threshold=0.85,
            session_metadata={"session_id": "sess_123"},
        )
        dumped = payload.model_dump()
        # entity_type is a category label, not the raw value — acceptable
        assert "entity_type" in dumped
        # Ensure no field named "raw_value", "entity_value", "text", etc.
        raw_keys = {"raw_value", "entity_value", "text", "original_text", "value"}
        assert raw_keys.isdisjoint(dumped.keys())

    def test_payload_with_optional_fields(self):
        """All optional fields are correctly populated."""
        now = datetime.now(UTC)
        payload = AmlEventPayload(
            event_id="evt_001",
            tenant_id="acme-corp",
            event_type="aml_test_alert",
            entity_type="PAYMENT_REF",
            confidence_score=0.88,
            threshold=0.80,
            timestamp=now,
            session_metadata={"session_id": "s1", "ip": "10.0.0.1"},
            alert_id="alert_abc",
        )
        assert payload.event_type == "aml_test_alert"
        assert payload.timestamp == now
        assert payload.alert_id == "alert_abc"


# ── AmlWebhookManager tests ────────────────────────────────────────────────


class TestAmlWebhookFiring:
    """Webhook fires/does-not-fire behavior."""

    @pytest.mark.asyncio
    async def test_fires_when_confidence_exceeds_threshold(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Webhook fires when entity confidence >= tenant threshold."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        fired = await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "sess_123"},
        )
        assert fired is True
        assert mock_http_client.post.called

    @pytest.mark.asyncio
    async def test_does_not_fire_below_threshold(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Webhook does not fire when confidence below threshold."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        fired = await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.50,
            session_metadata={"session_id": "sess_123"},
        )
        assert fired is False
        assert not mock_http_client.post.called

    @pytest.mark.asyncio
    async def test_configurable_threshold_per_tenant(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Different tenants have different thresholds."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        # Tenant A: 0.85 — 0.80 < 0.85 → not fired
        fired_a = await manager.evaluate_and_fire(
            tenant_id="tenant-a",
            entity_type="IBAN",
            confidence=0.80,
            session_metadata={"session_id": "s1"},
        )
        # Tenant B: 0.70 — 0.80 >= 0.70 → fired
        fired_b = await manager.evaluate_and_fire(
            tenant_id="tenant-b",
            entity_type="IBAN",
            confidence=0.80,
            session_metadata={"session_id": "s2"},
        )
        assert fired_a is False
        assert fired_b is True

    @pytest.mark.asyncio
    async def test_entity_type_filter(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Only configured entity types trigger webhook."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        # Tenant only monitors IBAN and PAYMENT_REF
        fired_iban = await manager.evaluate_and_fire(
            tenant_id="tenant-c",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "s1"},
        )
        fired_email = await manager.evaluate_and_fire(
            tenant_id="tenant-c",
            entity_type="EMAIL_ADDRESS",
            confidence=0.92,
            session_metadata={"session_id": "s1"},
        )
        assert fired_iban is True
        assert fired_email is False


class TestAmlWebhookPayload:
    """Webhook payload structure and metadata-only invariant."""

    @pytest.mark.asyncio
    async def test_payload_is_metadata_only(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Webhook POST body contains no raw entity values."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        fired = await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "sess_123"},
        )
        assert fired is True

        # Extract the POST call and verify payload
        call_kwargs = mock_http_client.post.call_args
        assert call_kwargs is not None
        json_payload = call_kwargs[1].get("json", {})
        raw_keys = {"raw_value", "entity_value", "text", "original_text", "value"}
        assert raw_keys.isdisjoint(json_payload.keys())
        assert "entity_type" in json_payload  # category label, OK


class TestAmlAuditEvent:
    """Audit event emission for AML webhook."""

    @pytest.mark.asyncio
    async def test_audit_event_emitted_on_fire(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """aml_webhook_fired audit event emitted when webhook fires."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "sess_123"},
        )
        mock_audit_emitter.assert_called_once()
        call_arg = mock_audit_emitter.call_args[1]
        assert call_arg.get("event_type") == "aml_webhook_fired"
        assert call_arg.get("tenant_id") == "acme-corp"

    @pytest.mark.asyncio
    async def test_no_audit_event_when_below_threshold(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """No audit event when webhook does not fire."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.50,
            session_metadata={"session_id": "sess_123"},
        )
        mock_audit_emitter.assert_not_called()


class TestAmlWebhookFailure:
    """Webhook delivery failure handling."""

    @pytest.mark.asyncio
    async def test_delivery_failure_non_blocking(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Webhook delivery failure is logged but does not raise."""

        from anonreq.governance.webhooks.aml import AmlWebhookManager

        mock_http_client.post.side_effect = httpx.RequestError(
            "Connection refused", request=MagicMock(),
        )

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        # Should NOT raise despite HTTP failure
        fired = await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "sess_123"},
        )
        # Non-blocking: still returns True (webhook fired, just failed delivery)
        assert fired is True

    @pytest.mark.asyncio
    async def test_timeout_is_logged_not_raised(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """HTTP timeout is logged but not raised as exception."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        mock_http_client.post.side_effect = httpx.TimeoutException(
            "Timeout", request=MagicMock(),
        )

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        # Should NOT raise
        fired = await manager.evaluate_and_fire(
            tenant_id="acme-corp",
            entity_type="IBAN",
            confidence=0.92,
            session_metadata={"session_id": "sess_123"},
        )
        assert fired is True


class TestAmlConfigCRUD:
    """AML webhook config CRUD via manager."""

    @pytest.mark.asyncio
    async def test_set_and_get_config(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Set config then get returns same config."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        config = AmlWebhookConfig(
            tenant_id="acme-corp",
            webhook_url="https://hooks.acme-corp.com/aml",
            threshold=0.90,
            enabled=True,
        )
        saved = await manager.set_config("acme-corp", config)
        assert saved.tenant_id == "acme-corp"
        assert saved.threshold == 0.90

        loaded = await manager.get_config("acme-corp")
        assert loaded is not None
        assert loaded.threshold == 0.90

    @pytest.mark.asyncio
    async def test_get_config_nonexistent_tenant(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Getting config for nonexistent tenant returns None."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        config = await manager.get_config("nonexistent-tenant")
        assert config is None

    @pytest.mark.asyncio
    async def test_set_config_updates_existing(
        self, mock_db_session: AsyncMock, mock_http_client: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Setting config for existing tenant updates it."""
        from anonreq.governance.webhooks.aml import AmlWebhookManager

        manager = AmlWebhookManager(
            db=mock_db_session,
            http_client=mock_http_client,
            emit_audit=mock_audit_emitter,
        )

        config_a = AmlWebhookConfig(
            tenant_id="acme-corp",
            webhook_url="https://hooks.acme-corp.com/aml/v1",
            threshold=0.85,
            enabled=True,
        )
        await manager.set_config("acme-corp", config_a)

        config_b = AmlWebhookConfig(
            tenant_id="acme-corp",
            webhook_url="https://hooks.acme-corp.com/aml/v2",
            threshold=0.90,
            enabled=True,
        )
        saved = await manager.set_config("acme-corp", config_b)
        assert saved.threshold == 0.90
        assert "v2" in saved.webhook_url
