"""SLO tracking and computation engine.

Provides:
- ``SLOCounter``: A data class representing raw counter state.
- ``SLOCompliance``: A data class representing the calculated compliance status.
- ``SLOEngine``: The core engine managing increments and compliance checks.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
import yaml

from anonreq.cache.manager import CacheManager


@dataclass
class SLOCounter:
    slo_name: str
    window_type: str    # "daily" | "monthly" | "24h" | "30d"
    window_key: str     # e.g. "2026-07-03" or "rolling"
    numerator: int
    denominator: int


@dataclass
class SLOCompliance:
    slo_name: str
    target: float
    current: float      # percentage or raw value (e.g. latency in ms)
    compliant: bool
    window_type: str
    window_key: str
    last_breach: datetime | None


class SLOEngine:
    def __init__(self, cache_manager: CacheManager, config_path: str = "config/slo.yaml") -> None:
        self._redis = cache_manager._redis
        self._targets = {}
        self._cooldown = 300
        
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                slo_cfg = data.get("slo", {})
                self._targets = slo_cfg.get("targets", {})
                self._cooldown = slo_cfg.get("breach_cooldown_seconds", 300)
        except Exception:
            # Fallback to defaults if config not found/invalid
            self._targets = {
                "success_rate": {
                    "target": 99.9,
                    "window_fixed": ["daily", "monthly"],
                    "window_rolling": ["24h", "30d"]
                },
                "p95_latency_ms": {
                    "target": 100.0,
                    "window_fixed": ["daily", "monthly"],
                    "window_rolling": ["24h", "30d"]
                },
                "fail_secure_rate": {
                    "target": 0.1,
                    "window_fixed": ["daily", "monthly"],
                    "window_rolling": ["24h", "30d"]
                },
                "audit_write_rate": {
                    "target": 99.99,
                    "window_fixed": ["daily", "monthly"],
                    "window_rolling": ["24h", "30d"]
                }
            }

    def _get_window_seconds(self, window_type: str) -> int:
        if window_type == "24h":
            return 86400
        elif window_type == "30d":
            return 30 * 86400
        return 0

    async def record_success(self, tenant_id: str, slo_name: str, latency_ms: int = 0) -> None:
        """Increment success and total counters for all configured windows."""
        await self._record_event(tenant_id, slo_name, success=True, latency_ms=latency_ms)

    async def record_failure(self, tenant_id: str, slo_name: str) -> None:
        """Increment failure/total counters for all configured windows."""
        await self._record_event(tenant_id, slo_name, success=False)

    async def record_latency(self, tenant_id: str, latency_ms: int) -> None:
        """Record latency observation for P95 computation."""
        # For p95_latency_ms, the event itself counts as success if <= target,
        # but the metric itself is calculated on the raw latency values.
        # So we record latency values to the latency sorted sets.
        now = time.time()
        dt = datetime.now(timezone.utc)
        daily_key = dt.strftime("%Y-%m-%d")
        monthly_key = dt.strftime("%Y-%m")
        unique_member = f"{latency_ms}:{uuid.uuid4()}"

        cfg = self._targets.get("p95_latency_ms", {})
        
        # Fixed Daily
        if "daily" in cfg.get("window_fixed", []):
            key = f"slo:{tenant_id}:p95_latency_ms:daily:{daily_key}:latencies"
            await self._redis.zadd(key, {unique_member: now})
            await self._redis.expire(key, 35 * 86400)

        # Fixed Monthly
        if "monthly" in cfg.get("window_fixed", []):
            key = f"slo:{tenant_id}:p95_latency_ms:monthly:{monthly_key}:latencies"
            await self._redis.zadd(key, {unique_member: now})
            await self._redis.expire(key, 90 * 86400)

        # Rolling windows
        for window_type in cfg.get("window_rolling", []):
            key = f"slo:{tenant_id}:p95_latency_ms:rolling:{window_type}:latencies"
            await self._redis.zadd(key, {unique_member: now})
            # Clean up old elements
            cutoff = now - self._get_window_seconds(window_type)
            await self._redis.zremrangebyscore(key, "-inf", cutoff)

    async def _record_event(self, tenant_id: str, slo_name: str, success: bool, latency_ms: int = 0) -> None:
        cfg = self._targets.get(slo_name)
        if not cfg:
            return

        now = time.time()
        dt = datetime.now(timezone.utc)
        daily_key = dt.strftime("%Y-%m-%d")
        monthly_key = dt.strftime("%Y-%m")
        unique_member = str(uuid.uuid4())

        # 1. Fixed Daily
        if "daily" in cfg.get("window_fixed", []):
            den_key = f"slo:{tenant_id}:{slo_name}:daily:{daily_key}:den"
            await self._redis.incr(den_key)
            await self._redis.expire(den_key, 35 * 86400)
            if success:
                num_key = f"slo:{tenant_id}:{slo_name}:daily:{daily_key}:num"
                await self._redis.incr(num_key)
                await self._redis.expire(num_key, 35 * 86400)

        # 2. Fixed Monthly
        if "monthly" in cfg.get("window_fixed", []):
            den_key = f"slo:{tenant_id}:{slo_name}:monthly:{monthly_key}:den"
            await self._redis.incr(den_key)
            await self._redis.expire(den_key, 90 * 86400)
            if success:
                num_key = f"slo:{tenant_id}:{slo_name}:monthly:{monthly_key}:num"
                await self._redis.incr(num_key)
                await self._redis.expire(num_key, 90 * 86400)

        # 3. Rolling Windows
        for window_type in cfg.get("window_rolling", []):
            window_seconds = self._get_window_seconds(window_type)
            den_key = f"slo:{tenant_id}:{slo_name}:rolling:{window_type}:den"
            num_key = f"slo:{tenant_id}:{slo_name}:rolling:{window_type}:num"

            # Add new record
            await self._redis.zadd(den_key, {unique_member: now})
            if success:
                await self._redis.zadd(num_key, {unique_member: now})

            # Cleanup expired records
            cutoff = now - window_seconds
            await self._redis.zremrangebyscore(den_key, "-inf", cutoff)
            await self._redis.zremrangebyscore(num_key, "-inf", cutoff)

    async def compute_compliance(self, tenant_id: str, slo_name: str | None = None) -> list[SLOCompliance]:
        """Compute SLO compliance for all windows."""
        slos_to_check = [slo_name] if slo_name else list(self._targets.keys())
        results = []
        now = time.time()
        dt = datetime.now(timezone.utc)
        daily_key = dt.strftime("%Y-%m-%d")
        monthly_key = dt.strftime("%Y-%m")

        for sname in slos_to_check:
            cfg = self._targets.get(sname)
            if not cfg:
                continue

            target = cfg["target"]

            # Helper to check compliance Boolean
            def is_compliant(current_val: float) -> bool:
                if sname == "success_rate" or sname == "audit_write_rate":
                    return current_val >= target
                else:  # fail_secure_rate or p95_latency_ms
                    return current_val <= target

            # Helper to fetch last breach timestamp
            async def get_last_breach(wtype: str) -> datetime | None:
                lb_key = f"slo:{tenant_id}:{sname}:{wtype}:last_breach"
                raw = await self._redis.get(lb_key)
                if raw:
                    try:
                        return datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
                    except Exception:
                        return None
                return None

            # 1. Evaluate p95_latency_ms
            if sname == "p95_latency_ms":
                # Fixed Daily
                if "daily" in cfg.get("window_fixed", []):
                    key = f"slo:{tenant_id}:p95_latency_ms:daily:{daily_key}:latencies"
                    latencies = await self._get_latencies_from_zset(key)
                    p95 = self._calculate_p95(latencies)
                    results.append(SLOCompliance(
                        slo_name=sname, target=target, current=p95, compliant=is_compliant(p95),
                        window_type="daily", window_key=daily_key, last_breach=await get_last_breach("daily")
                    ))

                # Fixed Monthly
                if "monthly" in cfg.get("window_fixed", []):
                    key = f"slo:{tenant_id}:p95_latency_ms:monthly:{monthly_key}:latencies"
                    latencies = await self._get_latencies_from_zset(key)
                    p95 = self._calculate_p95(latencies)
                    results.append(SLOCompliance(
                        slo_name=sname, target=target, current=p95, compliant=is_compliant(p95),
                        window_type="monthly", window_key=monthly_key, last_breach=await get_last_breach("monthly")
                    ))

                # Rolling Windows
                for wtype in cfg.get("window_rolling", []):
                    key = f"slo:{tenant_id}:p95_latency_ms:rolling:{wtype}:latencies"
                    # First evict old
                    cutoff = now - self._get_window_seconds(wtype)
                    await self._redis.zremrangebyscore(key, "-inf", cutoff)
                    latencies = await self._get_latencies_from_zset(key)
                    p95 = self._calculate_p95(latencies)
                    results.append(SLOCompliance(
                        slo_name=sname, target=target, current=p95, compliant=is_compliant(p95),
                        window_type=wtype, window_key="rolling", last_breach=await get_last_breach(wtype)
                    ))
                continue

            # 2. Evaluate rate-based/ratio SLOs
            # Fixed Daily
            if "daily" in cfg.get("window_fixed", []):
                den_key = f"slo:{tenant_id}:{sname}:daily:{daily_key}:den"
                num_key = f"slo:{tenant_id}:{sname}:daily:{daily_key}:num"
                den = int(await self._redis.get(den_key) or 0)
                num = int(await self._redis.get(num_key) or 0)
                current = (num / den * 100.0) if den > 0 else (0.0 if sname == "fail_secure_rate" else 100.0)
                results.append(SLOCompliance(
                    slo_name=sname, target=target, current=current, compliant=is_compliant(current),
                    window_type="daily", window_key=daily_key, last_breach=await get_last_breach("daily")
                ))

            # Fixed Monthly
            if "monthly" in cfg.get("window_fixed", []):
                den_key = f"slo:{tenant_id}:{sname}:monthly:{monthly_key}:den"
                num_key = f"slo:{tenant_id}:{sname}:monthly:{monthly_key}:num"
                den = int(await self._redis.get(den_key) or 0)
                num = int(await self._redis.get(num_key) or 0)
                current = (num / den * 100.0) if den > 0 else (0.0 if sname == "fail_secure_rate" else 100.0)
                results.append(SLOCompliance(
                    slo_name=sname, target=target, current=current, compliant=is_compliant(current),
                    window_type="monthly", window_key=monthly_key, last_breach=await get_last_breach("monthly")
                ))

            # Rolling Windows
            for wtype in cfg.get("window_rolling", []):
                den_key = f"slo:{tenant_id}:{sname}:rolling:{wtype}:den"
                num_key = f"slo:{tenant_id}:{sname}:rolling:{wtype}:num"

                # Evict old
                cutoff = now - self._get_window_seconds(wtype)
                await self._redis.zremrangebyscore(den_key, "-inf", cutoff)
                await self._redis.zremrangebyscore(num_key, "-inf", cutoff)

                den = await self._redis.zcard(den_key) or 0
                num = await self._redis.zcard(num_key) or 0
                current = (num / den * 100.0) if den > 0 else (0.0 if sname == "fail_secure_rate" else 100.0)
                results.append(SLOCompliance(
                    slo_name=sname, target=target, current=current, compliant=is_compliant(current),
                    window_type=wtype, window_key="rolling", last_breach=await get_last_breach(wtype)
                ))

        return results

    async def get_all_compliance(self, tenant_id: str) -> dict[str, list[SLOCompliance]]:
        """Get compliance for all configured SLOs keyed by slo_name."""
        compliance_list = await self.compute_compliance(tenant_id)
        grouped = {}
        for comp in compliance_list:
            grouped.setdefault(comp.slo_name, []).append(comp)
        return grouped

    async def _get_latencies_from_zset(self, key: str) -> list[float]:
        members = await self._redis.zrange(key, 0, -1)
        latencies = []
        for m in members:
            m_str = m.decode() if isinstance(m, bytes) else m
            try:
                latencies.append(float(m_str.split(":")[0]))
            except (ValueError, IndexError):
                pass
        return latencies

    def _calculate_p95(self, latencies: list[float]) -> float:
        if not latencies:
            return 0.0
        sorted_l = sorted(latencies)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]
