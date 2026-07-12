"""Shadow AI event generation with audit logging and webhook alerting.

Per D-001, D-025:
- Emits shadow_ai_detected event with correct event_type and fields
- Events contain metadata only (no raw query payloads)
- Configurable webhook alert integration
- Webhook call is fire-and-forget with configurable timeout (default 5s)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from anonreq.discovery.dns_parser import DNSEntry
from anonreq.discovery.hostname_matcher import MatchResult
from anonreq.discovery.proxy_parser import ProxyEntry

logger = logging.getLogger(__name__)


@dataclass
class ShadowAIEvent:
    """Event emitted when shadow AI usage is detected.

    Attributes:
        event_type: Always "shadow_ai_detected".
        source_ip: IP address of the client.
        destination_host: The AI service hostname.
        estimated_service: Name of the estimated AI service/provider.
        confidence: Detection confidence (0.0-1.0).
        detection_source: Source of detection — "dns" or "proxy".
        timestamp: When the event was generated.
        tenant_id: Tenant identifier for multi-tenant deployments.
    """

    event_type: str = "shadow_ai_detected"
    source_ip: str = ""
    destination_host: str = ""
    estimated_service: str = ""
    confidence: float = 0.0
    detection_source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, excluding raw/internal fields."""
        return {
            "event_type": self.event_type,
            "source_ip": self.source_ip,
            "destination_host": self.destination_host,
            "estimated_service": self.estimated_service,
            "confidence": self.confidence,
            "detection_source": self.detection_source,
            "timestamp": self.timestamp.isoformat(),
            "tenant_id": self.tenant_id,
        }


class EventGenerator:
    """Generates and emits shadow AI detection events.

    Args:
        audit_logger: Structured logger for audit events (must implement .info()).
        webhook_url: Optional HTTPS URL for webhook alerts.
        webhook_timeout: Timeout in seconds for webhook POST (default 5.0).
        tenant_id: Tenant identifier.
    """

    def __init__(
        self,
        audit_logger: Any,
        webhook_url: str | None = None,
        webhook_timeout: float = 5.0,
        tenant_id: str = "default",
    ) -> None:
        self._audit_logger = audit_logger
        self._webhook_url = webhook_url
        self._webhook_timeout = webhook_timeout
        self._tenant_id = tenant_id

    def generate_event(
        self,
        entry: DNSEntry | ProxyEntry,
        match: MatchResult,
    ) -> ShadowAIEvent:
        """Create a ShadowAIEvent from a matched DNS or proxy entry.

        Args:
            entry: The DNS or proxy entry that triggered detection.
            match: The match result identifying the AI provider.

        Returns:
            A ShadowAIEvent with populated fields.
        """
        detection_source = "dns" if isinstance(entry, DNSEntry) else "proxy"

        if isinstance(entry, DNSEntry):
            destination_host = entry.hostname
            source_ip = entry.source_ip
        else:
            destination_host = urlparse(entry.url).hostname or entry.url
            source_ip = entry.source_ip

        return ShadowAIEvent(
            source_ip=source_ip,
            destination_host=destination_host,
            estimated_service=match.provider,
            confidence=match.confidence,
            detection_source=detection_source,
            timestamp=datetime.now(UTC),
            tenant_id=self._tenant_id,
        )

    def emit(self, event: ShadowAIEvent) -> None:
        """Emit a shadow AI event to audit logger and optional webhook.

        Args:
            event: The ShadowAIEvent to emit.
        """
        event_dict = event.to_dict()

        self._audit_logger.info(
            "shadow_ai_detected",
            **event_dict,
        )

        if self._webhook_url:
            self._send_webhook(event_dict)

    def emit_batch(self, events: list[ShadowAIEvent]) -> None:
        """Emit multiple events in batch.

        Args:
            events: List of ShadowAIEvent to emit.
        """
        for event in events:
            self.emit(event)

    def _send_webhook(self, event_dict: dict[str, Any]) -> None:
        """Send event to webhook URL (fire-and-forget with timeout).

        Args:
            event_dict: The serialized event data.
        """
        try:
            with httpx.Client(timeout=self._webhook_timeout) as client:
                client.post(self._webhook_url, json=event_dict)
        except Exception:
            logger.warning("Webhook delivery failed", exc_info=True)
