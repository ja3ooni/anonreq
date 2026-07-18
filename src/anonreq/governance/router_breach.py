"""Breach notification endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import get_db

router = APIRouter()


@router.post("/breach/notify")
async def send_breach_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/breach/notify — send breach notifications."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    body = await request.json()
    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    result = await notifier.send_breach_notifications(
        breach_id=body["breach_id"],
        framework=body.get("framework", "gdpr"),
        description=body.get("description", ""),
        affected_tenants=body.get("affected_tenants", []),
    )
    return result


@router.get("/breach/queue")
async def get_breach_notification_queue(
    _request: Request,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/breach/queue — get notification queue."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    queue = await notifier.get_notification_queue(status=status)
    return {"object": "list", "data": queue}


@router.post("/breach/retry")
async def retry_failed_notifications(
    _request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/breach/retry — retry failed notifications."""
    from anonreq.breach.notifications import BreachNotifier
    from anonreq.breach.templates import BreachTemplateManager

    template_mgr = BreachTemplateManager()
    notifier = BreachNotifier(db=db, template_manager=template_mgr)
    count = await notifier.retry_failed_notifications()
    return {"retried": count}


@router.get("/breach/templates")
async def list_breach_templates(
    _request: Request,
) -> dict[str, Any]:
    """GET /v1/governance/breach/templates — list available templates."""
    from anonreq.breach.templates import BreachTemplateManager

    mgr = BreachTemplateManager()
    templates = mgr.list_available_templates()
    return {"object": "list", "data": templates}


@router.post("/breach/templates")
async def set_breach_custom_template(
    request: Request,
) -> dict[str, Any]:
    """POST /v1/governance/breach/templates — set custom template."""
    from anonreq.breach.templates import BreachTemplateManager
    from anonreq.models.breach import BreachTemplate

    body = await request.json()
    mgr = BreachTemplateManager()
    custom = BreachTemplate(
        id=body.get("id", f"custom-{body['framework']}-{body['region']}"),
        framework=body["framework"],
        region=body["region"],
        subject_template=body["subject_template"],
        body_template=body["body_template"],
    )

    await mgr.set_custom_template(body["framework"], body["region"], custom)
    return {"status": "ok", "template_id": custom.id}
