"""CASB enforcement engine — evaluates requests against policy.

Provides:
- CASBEvent: Audit event for CASB actions
- CASBEngine: Main enforcement engine with override support and telemetry
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from anonreq.casb.classifier import (
    AppPolicy,
    CASBClassifier,
    ClassificationAction,
)


@dataclass
class CASBEvent:
    """Audit event for a CASB enforcement action.

    Attributes:
        event_type: Type of event (unsanctioned_ai_access).
        application: App ID that triggered the event.
        user_id: Requesting user.
        tenant_id: Tenant identifier.
        groups: User's group memberships.
        action: Enforcement action taken.
        timestamp: When the event occurred.
    """

    event_type: str = "unsanctioned_ai_access"
    application: str = ""
    user_id: str = ""
    tenant_id: str = "default"
    groups: list[str] = field(default_factory=list)
    action: ClassificationAction = ClassificationAction.BLOCK
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dict (metadata only, no raw values)."""
        return {
            "event_type": self.event_type,
            "application": self.application,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "action": self.action.value if self.action else "block",
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EnforcementResult:
    """Result of a CASB enforcement decision.

    Attributes:
        action: Enforcement action taken.
        blocked: Whether the request was blocked.
        audit_event: Audit event if action generated one.
    """

    action: ClassificationAction
    blocked: bool = False
    audit_event: CASBEvent | None = None


class CASBEngine:
    """CASB enforcement engine.

    Evaluates requests against CASB app policies with per-group overrides.
    Provides telemetry and activity logging.

    Args:
        classifier: CASBClassifier instance.
        overrides: Dict of group_name -> {app_id: AppPolicy} for overrides.
    """

    def __init__(
        self,
        classifier: CASBClassifier,
        overrides: dict[str, dict[str, AppPolicy]] | None = None,
    ) -> None:
        self._classifier = classifier
        self._overrides = overrides or {}
        self._group_resolver: Callable[[str], list[str]] | None = None
        self._telemetry: dict[str, Any] = {
            "total_events": 0,
            "apps": {},
            "by_classification": {},
        }
        self._activity_log: list[CASBEvent] = []

    async def enforce(
        self,
        app_id: str,
        user_id: str,
        user_groups: list[str],
        tenant_id: str = "default",
    ) -> EnforcementResult:
        """Enforce CASB policy for an app request.

        Args:
            app_id: Application identifier.
            user_id: Requesting user.
            user_groups: User's group memberships.
            tenant_id: Tenant identifier.

        Returns:
            EnforcementResult with action and optional audit event.
        """
        # Check per-group overrides first
        for group in user_groups:
            if group in self._overrides:
                group_overrides = self._overrides[group]
                if app_id in group_overrides:
                    policy = group_overrides[app_id]
                    action = self._classifier.resolve_action(policy)
                    return EnforcementResult(
                        action=action,
                        blocked=(action == ClassificationAction.BLOCK),
                    )

        # Normal policy evaluation
        policy = self._classifier.classify(app_id)
        if policy is None:
            # Unknown app -> default block
            return self._record_enforcement(
                app_id=app_id,
                action=ClassificationAction.BLOCK,
                user_id=user_id,
                user_groups=user_groups,
                tenant_id=tenant_id,
                classification="unsanctioned",
            )

        action = self._classifier.resolve_action(policy)
        blocked = (action == ClassificationAction.BLOCK)

        # Generate audit event for all enforcements
        # ALLOW events are still recorded for activity log (telemetry)
        audit_event: CASBEvent | None = self._create_event(
            application=app_id,
            user_id=user_id,
            user_groups=user_groups,
            tenant_id=tenant_id,
            action=action,
        )
        # Only return audit_event for non-ALLOW actions
        returned_event = audit_event if action != ClassificationAction.ALLOW else None

        self._update_telemetry(app_id, policy.classification.value)
        return EnforcementResult(
            action=action,
            blocked=blocked,
            audit_event=returned_event,
        )

    def _record_enforcement(
        self,
        app_id: str,
        action: ClassificationAction,
        user_id: str,
        user_groups: list[str],
        tenant_id: str,
        classification: str,
    ) -> EnforcementResult:
        """Record an enforcement action and create audit event."""
        audit_event = self._create_event(
            application=app_id,
            user_id=user_id,
            user_groups=user_groups,
            tenant_id=tenant_id,
            action=action,
        )
        self._update_telemetry(app_id, classification)
        return EnforcementResult(
            action=action,
            blocked=(action == ClassificationAction.BLOCK),
            audit_event=audit_event if action != ClassificationAction.ALLOW else None,
        )

    def _create_event(
        self,
        application: str,
        user_id: str,
        user_groups: list[str],
        tenant_id: str,
        action: ClassificationAction,
    ) -> CASBEvent:
        """Create a CASB audit event."""
        event = CASBEvent(
            event_type="unsanctioned_ai_access",
            application=application,
            user_id=user_id,
            tenant_id=tenant_id,
            groups=list(user_groups),
            action=action,
        )
        self._activity_log.append(event)
        # Keep activity log bounded
        if len(self._activity_log) > 10000:
            self._activity_log = self._activity_log[-5000:]
        return event

    def _update_telemetry(self, app_id: str, classification: str) -> None:
        """Update telemetry counters."""
        self._telemetry["total_events"] += 1
        self._telemetry["apps"][app_id] = self._telemetry["apps"].get(app_id, 0) + 1
        self._telemetry["by_classification"][classification] = (
            self._telemetry["by_classification"].get(classification, 0) + 1
        )

    def get_telemetry(self) -> dict[str, Any]:
        """Get current telemetry snapshot."""
        return dict(self._telemetry)

    def query_activity(
        self,
        user_id: str | None = None,
        application: str | None = None,
        limit: int = 100,
    ) -> list[CASBEvent]:
        """Query activity log.

        Args:
            user_id: Optional filter by user.
            application: Optional filter by application.
            limit: Max results to return.

        Returns:
            List of matching CASBEvent objects.
        """
        results = list(self._activity_log)
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if application:
            results = [e for e in results if e.application == application]
        return results[:limit]

    def set_group_resolver(self, resolver: Callable[[str], list[str]]) -> None:
        """Set a callable to resolve user groups from user ID."""
        self._group_resolver = resolver

    def resolve_user_groups(self, user_id: str) -> list[str]:
        """Resolve user groups using the configured resolver.

        Args:
            user_id: User identifier.

        Returns:
            List of group names.
        """
        if self._group_resolver:
            return self._group_resolver(user_id)
        return []
