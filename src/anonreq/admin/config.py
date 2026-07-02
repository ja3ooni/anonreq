"""AtomicConfigRegistry — thread-safe pointer swap with version tracking.

Provides domain models (CustomRecognizerRule, ExclusionEntry, RulesConfig,
ConfigVersion) and AtomicConfigRegistry with thread-safe validation and swap.

Per D-147 through D-154:
- Hot-reloadable: custom recognizer patterns, confidence thresholds, exclusion lists
- Invalid config never replaces active config (AG-16, D-149)
- Thread-safe via Lock for both read and write (T-05-02-03)
- Version tracking with gauge metric update on success (D-154)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

from anonreq.monitoring.metrics import active_config_version

logger = logging.getLogger(__name__)


@dataclass
class CustomRecognizerRule:
    """A single custom recognizer rule with regex patterns.

    Attributes:
        id: Unique identifier for this rule.
        entity_type: The entity type label (e.g. "CUSTOM_ID", "PROJECT_CODE").
        patterns: List of regex pattern strings for detecting this entity.
        confidence: Confidence threshold (0.0 to 1.0, default 0.7).
        enabled: Whether this recognizer is active.
        version: Version number of this rule.
        created_at: Timestamp when this rule was created.
    """

    id: str
    entity_type: str
    patterns: list[str]
    confidence: float = 0.7
    enabled: bool = True
    version: int = 1
    created_at: datetime | None = None


@dataclass
class ExclusionEntry:
    """An exclusion entry for suppressing false positive detections.

    Attributes:
        value: The value to exclude (literal or wildcard pattern).
        match_type: How to match — "exact" or "wildcard".
        entity_type: Optional entity type to scope the exclusion.
    """

    value: str
    match_type: str  # "exact" | "wildcard"
    entity_type: str | None = None


@dataclass
class RulesConfig:
    """The complete custom rules configuration.

    Attributes:
        custom_recognizers: List of custom recognizer rules.
        exclusion_list: List of exclusion entries.
        thresholds: Dict of named threshold values (e.g. confidence).
    """

    custom_recognizers: list[CustomRecognizerRule]
    exclusion_list: list[ExclusionEntry]
    thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class ConfigVersion:
    """A versioned snapshot of the configuration.

    Attributes:
        version: Monotonically increasing version number.
        config: The RulesConfig at this version.
        applied_at: Timestamp when this version was applied.
        applied_by: Optional identifier of who applied it.
    """

    version: int
    config: RulesConfig
    applied_at: datetime
    applied_by: str | None = None


class AtomicConfigRegistry:
    """Thread-safe configuration registry with atomic pointer swap.

    Uses a Lock to protect both read and write operations on the current
    config and version. The validate_and_swap method holds the lock for
    the entire validation+swap cycle, preventing partial updates.

    Usage::

        registry = AtomicConfigRegistry()
        config = RulesConfig(custom_recognizers=[...], exclusion_list=[...])
        success, error = registry.validate_and_swap(config)
        if success:
            active = registry.get_active()
    """

    def __init__(self, initial_config: RulesConfig | None = None) -> None:
        """Initialize the registry.

        Args:
            initial_config: Starting configuration. If None, an empty
                config is used.
        """
        self._lock = Lock()
        self._current: RulesConfig = initial_config or RulesConfig(
            custom_recognizers=[],
            exclusion_list=[],
        )
        self._version: int = 0
        active_config_version.set(self._version)

    def get_active(self) -> RulesConfig:
        """Return the current active configuration.

        Returns:
            The current RulesConfig (thread-safe read).
        """
        with self._lock:
            return self._current

    def get_version(self) -> int:
        """Return the current configuration version number.

        Returns:
            The current version (0 = initial/default).
        """
        with self._lock:
            return self._version

    def validate_and_swap(self, new_config: RulesConfig) -> tuple[bool, str | None]:
        """Validate and atomically swap to a new configuration.

        Validation steps (D-148):
        1. Check all regex patterns compile
        2. Check exclusion entry match_type is valid
        3. If validation fails, return (False, error_message)
        4. If valid, atomically swap and increment version

        Args:
            new_config: The proposed new RulesConfig.

        Returns:
            A tuple of (success: bool, error_message: str | None).
            If success is True, error_message is None.
            If success is False, error_message describes the issue.
        """
        with self._lock:
            # Validate all regex patterns compile
            errors: list[str] = []
            for i, r in enumerate(new_config.custom_recognizers):
                for j, pat in enumerate(r.patterns):
                    try:
                        re.compile(pat)
                    except re.error as e:
                        errors.append(
                            f"recognizer[{i}].patterns[{j}]: {e.msg}"
                        )

            # Validate exclusion entry match_type
            for i, e in enumerate(new_config.exclusion_list):
                if e.match_type not in ("exact", "wildcard"):
                    errors.append(
                        f"exclusion_list[{i}].match_type: must be 'exact' or 'wildcard'"
                    )

            if errors:
                return False, "; ".join(errors)

            # Atomic swap
            self._current = new_config
            self._version += 1
            active_config_version.set(self._version)

            logger.info(
                "Custom rules config updated",
                extra={
                    "version": self._version,
                    "recognizer_count": len(new_config.custom_recognizers),
                    "exclusion_count": len(new_config.exclusion_list),
                },
            )
            return True, None
