"""Admin API routes for AML webhook configuration (D-014).

Provides CRUD operations for per-tenant AML webhook configuration
and a test endpoint to verify webhook delivery.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from anonreq.governance.webhooks.aml import AmlWebhookManager
from anonreq.middleware.rbac import require_role
from anonreq.models.governance import AmlEventPayload, AmlWebhookConfig

router = APIRouter(prefix="/aml/webhook", tags=["admin-aml"])


@router.get("/{tenant_id}")
async def get_aml_webhook_config(
    tenant_id: str,
    _: None = Depends(require_role("admin")),
) -> AmlWebhookConfig | dict[str, str]:
    """Get AML webhook configuration for a tenant."""
    manager = AmlWebhookManager()
    config = await manager.get_config(tenant_id)
    if config is None:
        raise HTTPException(status_code=404, detail="AML webhook not configured")
    return config


@router.put("/{tenant_id}")
async def set_aml_webhook_config(
    tenant_id: str,
    config: AmlWebhookConfig,
    _: None = Depends(require_role("admin")),
) -> AmlWebhookConfig:
    """Set or update AML webhook configuration for a tenant."""
    manager = AmlWebhookManager()
    saved = await manager.set_config(tenant_id, config)
    return saved


@router.post("/{tenant_id}/test")
async def test_aml_webhook(
    tenant_id: str,
    _: None = Depends(require_role("admin")),
) -> dict[str, str]:
    """Send a test AML webhook event for a tenant."""
    from anonreq.governance.webhooks.aml import AmlWebhookManager

    manager = AmlWebhookManager()
    config = await manager.get_config(tenant_id)
    if config is None:
        raise HTTPException(status_code=404, detail="AML webhook not configured")

    payload = AmlEventPayload(
        event_id=f"test_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        entity_type="AML_CASE_REF",
        confidence_score=0.95,
        threshold=config.threshold,
        session_metadata={"test": "true", "source": "admin_test"},
    )

    delivered = await manager.fire_webhook(payload, config)
    if delivered:
        return {"status": "delivered", "tenant_id": tenant_id}
    return {"status": "failed", "tenant_id": tenant_id, "detail": "Webhook delivery failed (see logs)"}
