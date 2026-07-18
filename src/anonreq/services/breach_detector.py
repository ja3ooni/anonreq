"""Breach detection, notification, and dead letter queue.

Provides:
- ``BreachEvent``: A data class representing a detected SLO breach.
- ``BreachDetector``: The core service detecting breaches, sending alerts, and managing DLQ.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
import yaml

from anonreq.cache.manager import CacheManager
from anonreq.models.audit import AuditEvent
from anonreq.services.audit_chain import AuditChainService
from anonreq.services.slo_engine import SLOEngine

logger = structlog.get_logger()


@dataclass
class BreachEvent:
    id: str
    slo_name: str
    target: float
    current_value: float
    window_type: str
    window_key: str
    tenant_id: str
    detected_at: datetime
    acknowledged: bool = False

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slo_name": self.slo_name,
            "target": self.target,
            "current_value": self.current_value,
            "window_type": self.window_type,
            "window_key": self.window_key,
            "tenant_id": self.tenant_id,
            "detected_at": self.detected_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


class BreachDetector:
    def __init__(
        self,
        slo_engine: SLOEngine,
        audit_chain: AuditChainService | None,
        cache_manager: CacheManager,
        http_client: httpx.AsyncClient,
        config_path: str = "config/webhook.yaml"
    ) -> None:
        self._slo_engine = slo_engine
        self._audit_chain = audit_chain
        self._redis = cache_manager._redis
        self._http_client = http_client

        self._webhook_url = os.environ.get("ANONREQ_BREACH_WEBHOOK_URL", "")
        self._retry_max = 3
        self._retry_backoff_base = 2.0
        self._timeout_seconds = 10
        self._dlq_max_entries = 1000
        self._headers = {
            "Content-Type": "application/json",
            "X-AnonReq-Event-Type": "slo_breach",
        }

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                cfg = data.get("webhook", {})
                slo_cfg = cfg.get("slo_breach", {})
                if not self._webhook_url:
                    self._webhook_url = slo_cfg.get("url", "")
                self._retry_max = slo_cfg.get("retry_max", 3)
                self._retry_backoff_base = slo_cfg.get("retry_backoff_base", 2.0)
                self._timeout_seconds = slo_cfg.get("timeout_seconds", 10)
                self._dlq_max_entries = slo_cfg.get("dlq_max_entries", 1000)
                self._headers = cfg.get("headers", self._headers)
        except Exception:
            pass

    async def evaluate(self, tenant_id: str) -> list[BreachEvent]:
        """Evaluate all SLOs for breaches. Returns list of new breaches."""
        compliance_list = await self._slo_engine.compute_compliance(tenant_id)
        new_breaches = []
        now_dt = datetime.now(UTC)

        for comp in compliance_list:
            if not comp.compliant:
                # Check cooldown
                lb_key = f"slo:{tenant_id}:{comp.slo_name}:{comp.window_type}:last_breach"
                raw = await self._redis.get(lb_key)
                is_cooldown_active = False
                if raw:
                    try:
                        last_b_dt = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)  # noqa: E501
                        elapsed = (now_dt - last_b_dt).total_seconds()
                        if elapsed < self._slo_engine._cooldown:
                            is_cooldown_active = True
                    except Exception:
                        pass

                if is_cooldown_active:
                    continue

                # Record breach timestamp for cooldown + compliance
                await self._redis.set(lb_key, now_dt.isoformat())

                # Create breach event
                event = BreachEvent(
                    id=str(uuid.uuid4()),
                    slo_name=comp.slo_name,
                    target=comp.target,
                    current_value=comp.current,
                    window_type=comp.window_type,
                    window_key=comp.window_key,
                    tenant_id=tenant_id,
                    detected_at=now_dt
                )
                new_breaches.append(event)

                # Log audit event
                if self._audit_chain:
                    audit_evt = AuditEvent(
                        event_id=str(uuid.uuid4()),
                        prev_hash=None,
                        hash="",
                        timestamp=now_dt,
                        tenant_id=tenant_id,
                        request_id=None,
                        policy_id=None,
                        decision=None,
                        provider=None,
                        latency_ms=None,
                        event_type="slo_breach_detected",
                        operator_id=None,
                        change_type=None,
                        prev_value_hash=None,
                        new_value_hash=None,
                        metadata_json=json.dumps({
                            "slo_name": comp.slo_name,
                            "target": comp.target,
                            "current_value": comp.current,
                            "window_type": comp.window_type,
                            "window_key": comp.window_key,
                        }),
                        retention_days=2557,
                    )
                    try:
                        await self._audit_chain.store_event(audit_evt)
                    except Exception as e:
                        logger.error("breach_detector.audit_failed", error=str(e))

                # Fire webhook
                task = asyncio.create_task(self._fire_webhook(event))
                task.add_done_callback(self._log_task_exception)

        return new_breaches

    async def _fire_webhook(self, event: BreachEvent) -> bool:
        """POST breach event to configured webhook URL.
        Retry 3x with exponential backoff.
        On final failure: add to DLQ."""
        if not self._webhook_url:
            await self._deliver_to_dlq(event)
            return False

        payload = {
            "event_type": "slo_breach_detected",
            "slo_name": event.slo_name,
            "target": event.target,
            "current": event.current_value,
            "window": event.window_type,
            "tenant_id": event.tenant_id,
            "detected_at": event.detected_at.isoformat(),
        }

        for attempt in range(self._retry_max):
            try:
                response = await self._http_client.post(
                    self._webhook_url,
                    json=payload,
                    headers=self._headers,
                    timeout=self._timeout_seconds
                )
                if 200 <= response.status_code < 300:
                    return True
            except Exception as e:
                logger.warning("breach_detector.webhook_failed", attempt=attempt+1, error=str(e))

            if attempt < self._retry_max - 1:
                sleep_seconds = self._retry_backoff_base * (2 ** attempt)
                await asyncio.sleep(sleep_seconds)

        # All retries failed
        await self._deliver_to_dlq(event)
        return False

    @staticmethod
    def _log_task_exception(task: asyncio.Task[object]) -> None:
        """Log exceptions from background webhook tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "breach_webhook_task_failed",
                error=str(exc),
            )

    async def _deliver_to_dlq(self, event: BreachEvent) -> None:
        """Store failed delivery in Valkey DLQ list (LPUSH)."""
        key = f"breach_dlq:{event.tenant_id}"
        await self._redis.lpush(key, json.dumps(event.model_dump()))
        await self._redis.ltrim(key, 0, self._dlq_max_entries - 1)

    async def get_dlq_entries(self, tenant_id: str, limit: int = 100) -> list[BreachEvent]:
        """Return DLQ entries (LRANGE)."""
        key = f"breach_dlq:{tenant_id}"
        raw_list = await self._redis.lrange(key, 0, limit - 1)
        entries = []
        for raw in raw_list:
            raw_str = raw.decode() if isinstance(raw, bytes) else raw
            try:
                data = json.loads(raw_str)
                data["detected_at"] = datetime.fromisoformat(data["detected_at"])
                entries.append(BreachEvent(**data))
            except Exception:
                pass
        return entries

    async def ack_dlq_entry(self, tenant_id: str, event_id: str) -> None:
        """Remove individual DLQ entry (LREM)."""
        key = f"breach_dlq:{tenant_id}"
        raw_list = await self._redis.lrange(key, 0, -1)
        for raw in raw_list:
            raw_str = raw.decode() if isinstance(raw, bytes) else raw
            try:
                data = json.loads(raw_str)
                if data.get("id") == event_id:
                    await self._redis.lrem(key, 0, raw)
                    break
            except Exception:
                pass

    async def retry_dlq(self, tenant_id: str) -> int:
        """Retry all DLQ entries. Returns count of successfully delivered."""
        key = f"breach_dlq:{tenant_id}"
        raw_list = await self._redis.lrange(key, 0, -1)
        delivered_count = 0

        for raw in raw_list:
            raw_str = raw.decode() if isinstance(raw, bytes) else raw
            try:
                data = json.loads(raw_str)
                dt = datetime.fromisoformat(data["detected_at"])
                data["detected_at"] = dt
                event = BreachEvent(**data)

                success = await self._fire_webhook_directly(event)
                if success:
                    await self._redis.lrem(key, 0, raw)
                    delivered_count += 1
            except Exception:
                pass
        return delivered_count

    async def _fire_webhook_directly(self, event: BreachEvent) -> bool:
        """Webhook delivery without retry backoff or DLQ queueing."""
        if not self._webhook_url:
            return False
        payload = {
            "event_type": "slo_breach_detected",
            "slo_name": event.slo_name,
            "target": event.target,
            "current": event.current_value,
            "window": event.window_type,
            "tenant_id": event.tenant_id,
            "detected_at": event.detected_at.isoformat(),
        }
        try:
            response = await self._http_client.post(
                self._webhook_url,
                json=payload,
                headers=self._headers,
                timeout=self._timeout_seconds
            )
            return bool(200 <= response.status_code < 300)
        except Exception:
            return False
