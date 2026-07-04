"""DLP audit logger with MITRE ATT&CK mapping (Plan 13-04, Task 1).

Provides:
- ``DLPAuditLogger``: Emits DLP audit events with MITRE technique IDs
  via the audit chain, with a field allowlist that prevents raw content
  from entering the audit log.

MITRE technique IDs are looked up from ``config/mitre_attack.yaml``
per DLP category.  Three audit event types:
- ``dlp_violation`` — per-detection DLP violation with MITRE technique
- ``dlp_exfiltration_detected`` — exfiltration encoding detection
- ``dlp_outbound_suppressed`` — outbound response suppression

Per D-013, D-014, and Req 10 (No PII in logs):
- All DLP audit events include MITRE technique IDs for compliance reporting
- No raw content, match_text, or encoded payloads ever enter audit events
- Field allowlist enforced via ``ALLOWED_FIELDS``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger("anonreq.dlp.audit")


class DLPAuditLogger:
    """DLP-specific audit logger with MITRE ATT&CK mapping.

    Emits structured DLP audit events through the existing audit chain.
    All event payloads are filtered through ``ALLOWED_FIELDS`` — no raw
    content ever reaches the audit log.

    Attributes:
        ALLOWED_FIELDS: Set of field names permitted in DLP audit events.
    """

    ALLOWED_FIELDS = {
        "dlp_category",
        "dlp_action",
        "dlp_detection_count",
        "dlp_mitre_technique_id",
        "dlp_mitre_technique_name",
        "dlp_exfiltration_method",
        "dlp_exfiltration_confidence",
        "dlp_outbound_suppressed",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with MITRE ATT&CK mapping config.

        Args:
            config: Either the full ``config/mitre_attack.yaml`` content
                (with ``mitre_attack`` top-level key) or the ``mitre_attack``
                section itself.  Must contain ``mappings`` and optionally
                ``default``.
        """
        mitre_section = config.get("mitre_attack", config)
        self._mappings: dict[str, dict[str, Any]] = mitre_section.get("mappings", {})
        self._default: dict[str, Any] = mitre_section.get("default", {})

    def _get_mitre_mapping(self, category: str) -> dict[str, Any]:
        """Look up MITRE technique info for a DLP category.

        Falls back to the default mapping if the category is not found.

        Args:
            category: DLP category name string (e.g. ``"PII"``).

        Returns:
            Dict with ``technique_id`` and ``technique_name`` keys.
        """
        mapping = self._mappings.get(category)
        if mapping is None:
            return self._default
        return mapping

    def _filter_fields(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Strip any fields not in the allowlist.

        Ensures no raw content fields leak into audit events.

        Args:
            entry: Raw event dict.

        Returns:
            Filtered event dict with only ALLOWED_FIELDS + standard fields.
        """
        # Always keep standard audit fields
        standard_fields = {
            "event_type",
            "timestamp",
            "tenant_id",
            "request_id",
        }
        allowed = standard_fields | self.ALLOWED_FIELDS
        return {k: v for k, v in entry.items() if k in allowed}

    async def log_dlp_violation(
        self,
        dlp_result: Any,
        ctx: Any,
    ) -> None:
        """Log DLP violation audit events — one per detection.

        Each detection's category is looked up in the MITRE mapping to
        include the corresponding technique ID.

        Args:
            dlp_result: ``DLPResult`` with ``detections`` list.
            ctx: ``ProcessingContext`` with ``audit_chain``, ``tenant_id``,
                ``request_id``.
        """
        if not hasattr(ctx, "audit_chain") or ctx.audit_chain is None:
            return

        for detection in dlp_result.detections:
            mitre = self._get_mitre_mapping(detection.category.value)
            entry = {
                "event_type": "dlp_violation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tenant_id": ctx.tenant_id,
                "request_id": ctx.request_id,
                "dlp_category": detection.category.value,
                "dlp_action": detection.action.value,
                "dlp_detection_count": len(dlp_result.detections),
                "dlp_mitre_technique_id": mitre.get("technique_id"),
                "dlp_mitre_technique_name": mitre.get("technique_name"),
                # NO match_text, NO original content, NO request body
            }
            await ctx.audit_chain.log_event("dlp_violation", **self._filter_fields(entry))

    async def log_dlp_exfiltration(
        self,
        exf_summary: Any,
        ctx: Any,
    ) -> None:
        """Log exfiltration detection audit event.

        Args:
            exf_summary: Object with ``methods`` (list of str),
                ``max_confidence`` (float), ``detection_count`` (int).
            ctx: ``ProcessingContext`` with ``audit_chain``.
        """
        if not hasattr(ctx, "audit_chain") or ctx.audit_chain is None:
            return

        mitre = self._get_mitre_mapping("Exfiltration")
        entry = {
            "event_type": "dlp_exfiltration_detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": ctx.tenant_id,
            "request_id": ctx.request_id,
            "dlp_exfiltration_method": ",".join(exf_summary.methods),
            "dlp_exfiltration_confidence": exf_summary.max_confidence,
            "dlp_detection_count": exf_summary.detection_count,
            "dlp_mitre_technique_id": mitre.get("technique_id"),
            "dlp_mitre_technique_name": mitre.get("technique_name"),
            # NO encoded content, NO match text
        }
        await ctx.audit_chain.log_event(
            "dlp_exfiltration_detected", **self._filter_fields(entry)
        )

    async def log_dlp_outbound_suppressed(self, ctx: Any) -> None:
        """Log outbound DLP suppression audit event.

        Args:
            ctx: ``ProcessingContext`` with ``audit_chain``.
        """
        if not hasattr(ctx, "audit_chain") or ctx.audit_chain is None:
            return

        mitre = self._get_mitre_mapping("Exfiltration")
        entry = {
            "event_type": "dlp_outbound_suppressed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": ctx.tenant_id,
            "request_id": ctx.request_id,
            "dlp_outbound_suppressed": True,
            "dlp_mitre_technique_id": mitre.get("technique_id"),
            "dlp_mitre_technique_name": mitre.get("technique_name"),
            # NO provider response content
        }
        await ctx.audit_chain.log_event(
            "dlp_outbound_suppressed", **self._filter_fields(entry)
        )
