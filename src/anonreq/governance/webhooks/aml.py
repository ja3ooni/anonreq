"""AML webhook with configurable tenant thresholds (D-014).

Fires an HTTP POST to the tenant's configured webhook URL when a
financial crime entity's confidence score exceeds the tenant's threshold.
Payload is metadata-only — no raw entity values. Delivery failures are
non-blocking (logged but pipeline unaffected).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from anonreq.models.governance import AmlEventPayload, AmlWebhookConfig

logger = logging.getLogger(__name__)

# In-memory store for tenant webhook configs (replaced by PostgreSQL in prod)
# Key: tenant_id, Value: AmlWebhookConfig
_aml_config_store: dict[str, AmlWebhookConfig] = {
    "acme-corp": AmlWebhookConfig(
        tenant_id="acme-corp",
        webhook_url="https://hooks.acme-corp.com/aml/alert",
        secret="whsec_test_secret_key_12345",
        enabled=True,
        threshold=0.85,
        entity_types=["IBAN", "PAYMENT_REF", "CUSTOMER_ID", "AML_CASE_REF"],
    ),
    "tenant-a": AmlWebhookConfig(
        tenant_id="tenant-a",
        webhook_url="https://hooks.tenant-a.com/aml",
        threshold=0.85,
        entity_types=["IBAN", "PAYMENT_REF"],
    ),
    "tenant-b": AmlWebhookConfig(
        tenant_id="tenant-b",
        webhook_url="https://hooks.tenant-b.com/aml",
        threshold=0.70,
        entity_types=["IBAN", "PAYMENT_REF", "CUSTOMER_ID", "AML_CASE_REF"],
    ),
    "tenant-c": AmlWebhookConfig(
        tenant_id="tenant-c",
        webhook_url="https://hooks.tenant-c.com/aml",
        threshold=0.80,
        entity_types=["IBAN", "PAYMENT_REF"],
    ),
}


class AmlWebhookManager:
    """Manages AML webhook configuration and firing.

    Loads per-tenant config, evaluates whether an entity confidence
    score exceeds the configured threshold, and fires the webhook via
    HTTP POST with an HMAC-signed metadata-only payload.

    Args:
        db: Async SQLAlchemy session (reserved for future PostgreSQL storage).
        http_client: httpx.AsyncClient for outbound webhook calls.
        emit_audit: Callable for emitting audit events. Receives
            ``event_type``, ``tenant_id``, and ``metadata_json`` kwargs.
    """

    def __init__(
        self,
        db: Any = None,
        http_client: httpx.AsyncClient | None = None,
        emit_audit: Callable[..., Any] | None = None,
    ) -> None:
        self._db = db
        self._http_client = http_client or httpx.AsyncClient(timeout=5.0)
        self._emit_audit = emit_audit or _noop_audit

    async def get_config(self, tenant_id: str) -> AmlWebhookConfig | None:
        """Load the AML webhook config for a tenant.

        Currently uses in-memory store. Will be migrated to PostgreSQL.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The config if found, or None.
        """
        return _aml_config_store.get(tenant_id)

    async def set_config(
        self, tenant_id: str, config: AmlWebhookConfig,
    ) -> AmlWebhookConfig:
        """Set or update the AML webhook config for a tenant.

        Args:
            tenant_id: The tenant identifier.
            config: The new webhook configuration.

        Returns:
            The saved config.
        """
        # Ensure tenant_id is consistent
        config.tenant_id = tenant_id
        _aml_config_store[tenant_id] = config
        return config

    async def evaluate_and_fire(
        self,
        tenant_id: str,
        entity_type: str,
        confidence: float,
        session_metadata: dict[str, str],
    ) -> bool:
        """Evaluate whether to fire the AML webhook and fire if needed.

        Steps:
        1. Load tenant webhook config.
        2. If config not found or disabled, return False.
        3. If confidence < threshold, return False.
        4. If entity_type not in configured types, return False.
        5. Build metadata-only payload.
        6. POST to webhook URL (non-blocking failure).
        7. Emit audit event.
        8. Return True if webhook was fired (regardless of delivery).

        Args:
            tenant_id: The tenant identifier.
            entity_type: The detected entity type label.
            confidence: The confidence score (0.0–1.0).
            session_metadata: Session metadata dict (no raw values).

        Returns:
            True if the webhook was fired (regardless of delivery outcome).
        """
        config = await self.get_config(tenant_id)
        if config is None or not config.enabled:
            return False

        # Check threshold
        if confidence < config.threshold:
            return False

        # Check entity type filter
        if config.entity_types is not None and entity_type not in config.entity_types:
            return False

        # Build payload
        payload = AmlEventPayload(
            event_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_type=entity_type,
            confidence_score=confidence,
            threshold=config.threshold,
            timestamp=datetime.now(timezone.utc),
            session_metadata=session_metadata,
            alert_id=f"aml_{uuid.uuid4().hex[:12]}",
        )

        # Fire webhook (non-blocking on failure)
        await self.fire_webhook(payload, config)

        # Emit audit event
        self._emit_audit(
            event_type="aml_webhook_fired",
            tenant_id=tenant_id,
            metadata_json=payload.model_dump_json(),
        )

        return True

    async def fire_webhook(
        self,
        payload: AmlEventPayload,
        config: AmlWebhookConfig,
    ) -> bool:
        """Send the AML alert payload to the configured webhook URL.

        Builds an HMAC-SHA256 signature header if a secret is configured.
        On delivery failure, logs a warning and returns False (non-blocking).

        Args:
            payload: The event payload to send.
            config: The tenant's webhook configuration.

        Returns:
            True if delivery succeeded, False on failure.
        """
        body = payload.model_dump(mode="json")
        body_str = json.dumps(body, default=str)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-AML-Event-ID": payload.event_id,
            "X-AML-Tenant-ID": payload.tenant_id,
        }

        # HMAC-SHA256 signature
        if config.secret:
            signature = hmac.new(
                config.secret.encode("utf-8"),
                body_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            headers["X-AML-Signature"] = f"sha256={signature}"

        try:
            response = await self._http_client.post(
                config.webhook_url,
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            logger.info(
                "AML webhook delivered",
                extra={
                    "tenant_id": payload.tenant_id,
                    "event_id": payload.event_id,
                    "status_code": response.status_code,
                },
            )
            return True
        except httpx.RequestError as exc:
            logger.warning(
                "AML webhook delivery failed (non-blocking)",
                extra={
                    "tenant_id": payload.tenant_id,
                    "event_id": payload.event_id,
                    "error": str(exc),
                },
            )
            return False
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "AML webhook returned non-2xx (non-blocking)",
                extra={
                    "tenant_id": payload.tenant_id,
                    "event_id": payload.event_id,
                    "status_code": exc.response.status_code,
                },
            )
            return False


def _noop_audit(**kwargs: Any) -> None:
    """No-op audit emitter for tests without audit infrastructure."""
    pass
