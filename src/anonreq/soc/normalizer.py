"""SOC event normalizer — content stripping, MITRE mapping, and metadata enrichment.

Per D-011, D-012, D-021:
- Consumes RawSecurityEvent from detection engines via asyncio.Queue
- Strips raw content fields (content, prompt, response, raw_text, etc.)
- Applies MITRE technique ID mapping via MITREMapper
- Enriches events with gateway_version and appliance_instance_id
- Events containing content fields are dropped with soc_strip_failure audit
- Non-blocking put prevents detection engine blocking on SOC delivery
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from prometheus_client import Counter

from anonreq.soc.event import NormalizedEvent, RawSecurityEvent, SeverityLevel

logger = logging.getLogger("anonreq.soc.normalizer")

# Field names that indicate raw content — if present, the event is dropped
# per D-012 fail-secure policy. Case-insensitive matching uses .lower().
STRIP_FIELDS: set[str] = {
    "content",
    "prompt",
    "response",
    "raw_text",
    "message",
    "text",
}

# Prometheus counters
soc_events_normalized = Counter(
    "anonreq_soc_events_normalized_total",
    "Events processed by the SOC normalizer",
    ["source_engine"],
)

soc_strip_failures = Counter(
    "anonreq_soc_strip_failures_total",
    "Events dropped due to content field detection",
    ["source_engine"],
)


class SOCNormalizer:
    """SOC event normalizer — ingests raw events, normalizes, fans out.

    Subscribes to security events from detection engines via an internal
    ``asyncio.Queue`` event bus, strips raw content fields, applies MITRE
    technique ID mapping, enriches metadata, and fans out normalized events
    to registered sink callbacks.

    Args:
        mitre_mapper: ``MITREMapper`` instance for technique ID resolution.
        config: ``SOCConfig`` with version and instance identity.
        audit_logger: Optional async audit logger for soc events.
        metrics_registry: Optional Prometheus registry (defaults to global).
    """

    def __init__(
        self,
        mitre_mapper: Any,
        config: Any,
        audit_logger: Any | None = None,
        _metrics_registry: Any | None = None,
    ) -> None:
        self._mitre_mapper = mitre_mapper
        self._config = config
        self._audit_logger = audit_logger
        self._sink_callbacks: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._task: asyncio.Task[None] | None = None

        # Internal event bus — detection engines publish here
        self.event_bus: asyncio.Queue[RawSecurityEvent] = asyncio.Queue(
            maxsize=config.event_bus_maxsize
        )

    def publish_raw(self, raw: RawSecurityEvent) -> None:
        """Publish a raw security event to the event bus (non-blocking).

        Uses ``put_nowait`` per D-021 — never blocks detection engine
        processing on SOC delivery.

        Args:
            raw: The raw security event from a detection engine.
        """
        try:
            self.event_bus.put_nowait(raw)
        except asyncio.QueueFull:
            logger.warning(
                "SOC event bus full — event dropped",
                extra={
                    "source_engine": raw.source_engine,
                    "event_type": raw.event_type,
                },
            )

    def register_sink_callback(
        self, sink_name: str, callback: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        """Register a sink callback to receive normalized events.

        Args:
            sink_name: Unique name for this sink.
            callback: Async callable that accepts ``NormalizedEvent``.
        """
        self._sink_callbacks[sink_name] = callback

    async def start(self) -> None:
        """Start the background consume loop as an asyncio task."""
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Cancel the background consume loop and drain pending events."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._drain()

    async def _consume_loop(self) -> None:
        """Background loop consuming events from the event bus."""
        while True:
            try:
                raw = await self.event_bus.get()
                normalized = await self._normalize(raw)
                if normalized is not None:
                    await self._fan_out(normalized)
                self.event_bus.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in SOC normalizer consume loop")
                self.event_bus.task_done()

    async def _consume_one(self) -> None:
        """Process a single event from the bus (for testing)."""
        raw = await self.event_bus.get()
        normalized = await self._normalize(raw)
        if normalized is not None:
            await self._fan_out(normalized)
        self.event_bus.task_done()

    async def _normalize(self, raw: RawSecurityEvent) -> NormalizedEvent | None:
        """Normalize a raw security event into a NormalizedEvent.

        Steps:
        1. Strip content fields from the event payload
        2. If content was detected: drop event, emit audit, return None
        3. Apply MITRE technique ID mapping
        4. Build NormalizedEvent with enriched metadata

        Args:
            raw: Raw security event from detection engine.

        Returns:
            NormalizedEvent or None if content was detected and stripped.
        """
        stripped = self._strip_content_fields(raw.content)
        if self._content_stripped:
            logger.warning(
                "Content fields stripped from security event — dropping",
                extra={
                    "source_engine": raw.source_engine,
                    "event_type": raw.event_type,
                },
            )
            soc_strip_failures.labels(source_engine=raw.source_engine).inc()
            if self._audit_logger is not None:
                await self._audit_logger.log_event(
                    "soc_strip_failure",
                    event_type=raw.event_type,
                    source_engine=raw.source_engine,
                    tenant_id=raw.tenant_id,
                    session_id=raw.session_id,
                )
            return None

        # Resolve MITRE technique ID
        mitre_id = self._mitre_mapper.resolve(raw.event_type)

        # Determine severity from raw content metadata
        severity = self._parse_severity(raw.content.get("severity", ""))

        # Count event
        soc_events_normalized.labels(source_engine=raw.source_engine).inc()

        return NormalizedEvent(
            severity=severity,
            event_type=raw.event_type,
            tenant_id=raw.tenant_id,
            session_id=raw.session_id,
            timestamp=raw.timestamp,
            gateway_version=self._config.gateway_version,
            appliance_instance_id=self._config.appliance_instance_id,
            mitre_technique_id=mitre_id,
            metadata=stripped,
        )

    def _strip_content_fields(self, content: dict[str, Any]) -> dict[str, Any]:
        """Remove raw content fields from event payload.

        Per D-012: fields named ``content``, ``prompt``, ``response``,
        ``raw_text``, ``message``, ``text`` are stripped (case-insensitive).
        The ``_content_stripped`` flag is set if any fields were removed.

        Args:
            content: Raw event content dict.

        Returns:
            Dict with content fields removed. Any remaining metadata fields
            are kept as-is (safe for SIEM forwarding).
        """
        stripped: dict[str, Any] = {}
        found = False
        for key, value in content.items():
            if key.lower() in STRIP_FIELDS:
                found = True
                continue
            stripped[key] = value
        self._content_stripped = found
        return stripped

    def _parse_severity(self, severity_str: str) -> SeverityLevel:
        """Parse a severity string into a SeverityLevel enum.

        Args:
            severity_str: Severity string from event content.

        Returns:
            Corresponding SeverityLevel, or INFORMATIONAL if unknown.
        """
        mapping = {
            "informational": SeverityLevel.INFORMATIONAL,
            "info": SeverityLevel.INFORMATIONAL,
            "low": SeverityLevel.LOW,
            "medium": SeverityLevel.MEDIUM,
            "high": SeverityLevel.HIGH,
            "critical": SeverityLevel.CRITICAL,
        }
        return mapping.get(severity_str.lower(), SeverityLevel.INFORMATIONAL)

    async def _fan_out(self, event: NormalizedEvent) -> None:
        """Send a normalized event to all registered sink callbacks.

        Args:
            event: The normalized event to distribute.
        """
        for sink_name, callback in self._sink_callbacks.items():
            try:
                await callback(event)
            except Exception:
                logger.exception(
                    "Sink callback failed for '%s'",
                    sink_name,
                    extra={
                        "sink_name": sink_name,
                        "event_type": event.event_type,
                    },
                )

    def _drain(self) -> None:
        """Drain remaining events from the event bus on shutdown."""
        drained = 0
        while not self.event_bus.empty():
            try:
                self.event_bus.get_nowait()
                self.event_bus.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained:
            logger.info("Drained %d events from SOC event bus", drained)
