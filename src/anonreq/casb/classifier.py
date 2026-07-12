"""CASB app classification policy loader and classifier.

Provides:
- AppClassification: 3-tier classification (sanctioned/tolerated/unsanctioned)
- ClassificationAction: Enforcement action (allow/alert/block)
- AppPolicy: Per-app policy configuration
- CASBClassifier: Classifies apps by ID or hostname, resolves actions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AppClassification(StrEnum):
    """3-tier CASB app classification."""

    SANCTIONED = "sanctioned"
    TOLERATED = "tolerated"
    UNSANCTIONED = "unsanctioned"


class ClassificationAction(StrEnum):
    """Enforcement action for classified apps."""

    ALLOW = "allow"
    ALERT = "alert"
    BLOCK = "block"


@dataclass
class AppPolicy:
    """Per-application CASB policy configuration.

    Attributes:
        app_id: Unique application identifier.
        classification: 3-tier classification level.
        risk_score: Numeric risk score (0-100).
        allowed_groups: User groups permitted to use the app.
        action: Enforcement action (defaults based on classification).
        notes: Optional notes about the policy.
    """

    app_id: str
    classification: AppClassification
    risk_score: int = 0
    allowed_groups: list[str] = field(default_factory=list)
    action: ClassificationAction | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        """Set default action based on classification if not specified."""
        if self.action is None:
            if self.classification == AppClassification.SANCTIONED:
                self.action = ClassificationAction.ALLOW
            elif self.classification == AppClassification.TOLERATED:
                self.action = ClassificationAction.ALERT
            else:
                self.action = ClassificationAction.BLOCK


class CASBClassifier:
    """Classifies AI SaaS applications and resolves enforcement actions.

    Args:
        policies: Dict of app_id -> AppPolicy.
    """

    def __init__(self, policies: dict[str, AppPolicy]) -> None:
        self._policies = dict(policies) if policies else {}
        self._hostname_map: dict[str, str] = {}  # hostname -> app_id

    def classify(self, app_id: str) -> AppPolicy | None:
        """Classify an app by its app_id.

        Args:
            app_id: Application identifier.

        Returns:
            AppPolicy if found, None if unknown.
        """
        return self._policies.get(app_id)

    def resolve_action(self, policy: AppPolicy) -> ClassificationAction:
        """Resolve the enforcement action for a policy.

        Args:
            policy: The app's policy.

        Returns:
            ClassificationAction for this app.
        """
        return policy.action or ClassificationAction.BLOCK

    def is_user_allowed(self, policy: AppPolicy, user_group: str) -> bool:
        """Check if a user group is allowed to use the app.

        Args:
            policy: The app's policy.
            user_group: User's group membership.

        Returns:
            True if the user group is in the allowed list.
        """
        if not policy.allowed_groups:
            return False
        return user_group in policy.allowed_groups

    def get_risk_score(self, app_id: str) -> int | None:
        """Get the risk score for an app.

        Args:
            app_id: Application identifier.

        Returns:
            Risk score or None if app not found.
        """
        policy = self._policies.get(app_id)
        return policy.risk_score if policy else None

    def list_apps(self) -> list[str]:
        """List all configured app IDs.

        Returns:
            List of app IDs.
        """
        return list(self._policies.keys())

    def set_hostname_mapping(self, mapping: dict[str, str]) -> None:
        """Set hostname-to-app_id mapping.

        Args:
            mapping: Dict of hostname -> app_id.
        """
        self._hostname_map.update(mapping)

    def classify_by_hostname(self, hostname: str) -> AppPolicy | None:
        """Classify an app by its hostname.

        Args:
            hostname: The hostname to look up.

        Returns:
            AppPolicy if the hostname maps to a known app.
        """
        app_id = self._hostname_map.get(hostname)
        if app_id:
            return self._policies.get(app_id)
        return None

    @classmethod
    def from_yaml(cls, yaml_config: dict[str, Any]) -> CASBClassifier:
        """Create classifier from Phase 8 YAML config.

        Args:
            yaml_config: Dict with 'apps' section containing app configs.

        Returns:
            CASBClassifier with parsed policies.

        Raises:
            ValueError: If config is invalid.
        """
        policies: dict[str, AppPolicy] = {}
        apps_section = yaml_config.get("apps", {})

        for app_id, config in apps_section.items():
            classification_str = config.get("classification", "unsanctioned")
            try:
                classification = AppClassification(classification_str)
            except ValueError:
                raise ValueError(f"Unknown classification '{classification_str}' for app '{app_id}'")  # noqa: B904, E501

            risk_score = config.get("risk_score", 50)
            if not isinstance(risk_score, int) or not (0 <= risk_score <= 100):
                raise ValueError(f"risk_score must be 0-100 for app '{app_id}'")

            action_str = config.get("action")
            action: ClassificationAction | None = None
            if action_str:
                try:
                    action = ClassificationAction(action_str)
                except ValueError:
                    raise ValueError(f"Unknown action '{action_str}' for app '{app_id}'")  # noqa: B904

            policy = AppPolicy(
                app_id=app_id,
                classification=classification,
                risk_score=risk_score,
                allowed_groups=config.get("allowed_groups", []),
                action=action,
                notes=config.get("notes"),
            )
            policies[app_id] = policy

        return cls(policies)
