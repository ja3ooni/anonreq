"""Shared dependencies for governance routers."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anonreq.models.audit import AuditEvent
from anonreq.state import get_app_state

logger = structlog.get_logger()


def _log_task_exception(task: asyncio.Task[object]) -> None:
    """Log exceptions from background tasks to prevent silent failures."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "background_task_failed",
            error=str(exc),
            task_name=task.get_name(),
        )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    engine = get_app_state(request.app).audit_engine
    if engine is None:
        raise RuntimeError("Audit engine not initialized")
    async with async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )() as session:
        yield session


def _emit_sync(
    request: Request,
    tenant_id: str,
    event_type: str,
    operator_id: str | None = None,
    metadata_json: str | None = None,
) -> None:
    """Fire-and-forget audit event emission."""
    chain = get_app_state(request.app).audit_chain
    if chain is None:
        return

    async def _emit() -> None:
        event = AuditEvent(
            event_id=f"gov_{uuid.uuid4().hex[:24]}",
            prev_hash=None,
            hash="",
            timestamp=datetime.now(UTC),
            tenant_id=tenant_id,
            request_id=getattr(request.state, "request_id", None),
            policy_id=None,
            decision=None,
            provider=None,
            latency_ms=None,
            event_type=event_type,
            operator_id=operator_id,
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json=metadata_json,
        )
        with contextlib.suppress(Exception):
            await chain.store_event(event)

    _task = asyncio.ensure_future(_emit())
    _task.add_done_callback(_log_task_exception)
