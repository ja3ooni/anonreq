"""Business logic and rate limiting for Trust Center public endpoints."""

from __future__ import annotations

import time
import structlog
from fastapi import HTTPException, Request
from prometheus_client import REGISTRY

from anonreq.cache.manager import CacheManager
from anonreq.services.slo_engine import SLOEngine
from anonreq.compliance.engine import PresetEngine
from anonreq.trust_center.config import TrustCenterSettings
from anonreq.trust_center.schemas import (
    FrameworkInfo,
    TrustCompliance,
    TrustMetrics,
    TrustSecurity,
    TrustStatus,
)

logger = structlog.get_logger()


class TrustCenterService:
    """Service providing aggregate metadata for Trust Center endpoints."""

    def __init__(
        self,
        slo_engine: SLOEngine,
        preset_engine: PresetEngine | None,
        settings: TrustCenterSettings,
    ) -> None:
        self._slo_engine = slo_engine
        self._preset_engine = preset_engine
        self._settings = settings
        self._startup_time = time.time()

    async def get_status(self) -> TrustStatus | None:
        """Get overall SLO compliance status."""
        try:
            grouped = await self._slo_engine.get_all_compliance("default")
        except Exception as exc:
            logger.error(
                "Failed to fetch SLO compliance from engine",
                error=str(exc),
                component="trust_center",
            )
            return None

        if not grouped:
            return TrustStatus(
                slo_count=0,
                compliant_count=0,
                overall_percentage=100.0,
                last_breach=None,
                period="Last 30 days",
            )

        total_slos = len(grouped)
        compliant_slos = 0
        last_breach = None

        for _, compliance_list in grouped.items():
            is_compliant = any(c.compliant for c in compliance_list)
            if is_compliant:
                compliant_slos += 1
            for c in compliance_list:
                if c.last_breach:
                    if last_breach is None or c.last_breach > last_breach:
                        last_breach = c.last_breach

        overall_percentage = (
            (compliant_slos / total_slos * 100.0) if total_slos > 0 else 100.0
        )

        return TrustStatus(
            slo_count=total_slos,
            compliant_count=compliant_slos,
            overall_percentage=round(overall_percentage, 2),
            last_breach=last_breach,
            period="Last 30 days",
        )

    async def get_compliance(self) -> TrustCompliance | None:
        """Get compliance framework information."""
        if self._preset_engine is None:
            return TrustCompliance(frameworks=[])

        try:
            presets = self._preset_engine.list_presets()
            frameworks = [
                FrameworkInfo(
                    id=preset.id,
                    name=preset.name,
                    description=preset.description,
                    jurisdictions=preset.jurisdictions,
                )
                for preset in presets.values()
            ]
            frameworks.sort(key=lambda f: f.id)
            return TrustCompliance(frameworks=frameworks)
        except Exception as exc:
            logger.error(
                "Failed to fetch presets from PresetEngine",
                error=str(exc),
                component="trust_center",
            )
            return None

    def get_metrics(self) -> TrustMetrics:
        """Get aggregate metrics from Prometheus registry and local state."""
        total_requests = 0.0
        total_entities = 0.0
        fail_secure_count = 0.0
        overhead_count = 0.0
        overhead_sum = 0.0
        buckets: dict[str, float] = {}

        for metric in REGISTRY.collect():
            if metric.name == "anonreq_requests_total":
                for sample in metric.samples:
                    if sample.name == "anonreq_requests_total":
                        total_requests += sample.value
            elif metric.name == "anonreq_entities_detected_total":
                for sample in metric.samples:
                    if sample.name == "anonreq_entities_detected_total":
                        total_entities += sample.value
            elif metric.name == "anonreq_fail_secure_events_total":
                for sample in metric.samples:
                    if sample.name == "anonreq_fail_secure_events_total":
                        fail_secure_count += sample.value
            elif metric.name == "anonreq_processing_overhead_ms":
                for sample in metric.samples:
                    if sample.name == "anonreq_processing_overhead_ms_count":
                        overhead_count += sample.value
                    elif sample.name == "anonreq_processing_overhead_ms_sum":
                        overhead_sum += sample.value
                    elif sample.name == "anonreq_processing_overhead_ms_bucket":
                        le = sample.labels.get("le")
                        if le:
                            buckets[le] = buckets.get(le, 0.0) + sample.value

        latency_p50_ms = 0.0
        latency_p99_ms = 0.0
        if overhead_count > 0:
            bucket_values = [5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, float("inf")]
            target_p50 = overhead_count * 0.50
            target_p99 = overhead_count * 0.99

            p50_val = None
            p99_val = None
            for b in bucket_values:
                b_str = "+Inf" if b == float("inf") else str(int(b))
                val = buckets.get(b_str, 0.0)
                if p50_val is None and val >= target_p50:
                    p50_val = b
                if p99_val is None and val >= target_p99:
                    p99_val = b

            latency_p50_ms = p50_val if p50_val is not None else 0.0
            latency_p99_ms = p99_val if p99_val is not None else 0.0

        uptime_days = round((time.time() - self._startup_time) / 86400.0, 2)

        return TrustMetrics(
            total_requests=total_requests,
            total_entities=total_entities,
            fail_secure_count=fail_secure_count,
            latency_p50_ms=float(latency_p50_ms),
            latency_p99_ms=float(latency_p99_ms),
            uptime_days=uptime_days,
        )

    def get_security(self) -> TrustSecurity:
        """Get security posture information from settings."""
        return TrustSecurity(
            display_name=self._settings.display_name,
            contact_email=self._settings.contact_email,
            logo_url=self._settings.logo_url,
            feature_summary=self._settings.feature_summary,
            security_contact=self._settings.security_contact,
            certifications=self._settings.certifications,
        )


class TrustCenterRateLimiter:
    """IP-based rate limiter for public Trust Center endpoints."""

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def __call__(self, request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        current_minute = int(time.time() / 60)
        key = f"trust_rate:{client_host}:{current_minute}"

        count = await self._redis.get(key)
        if count is None:
            # First request in this minute window
            # Set key to 1 with a 65s TTL
            await self._redis.set(key, "1", ex=65)
            return

        try:
            int_count = int(count.decode() if isinstance(count, bytes) else count)
        except ValueError:
            int_count = 0

        if int_count >= 60:
            raise HTTPException(
                status_code=429,
                detail="rate_limit_exceeded",
            )

        await self._redis.incr(key)
