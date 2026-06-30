"""Classification engine — YAML-based 4-tier rule evaluation.

Per D-22 through D-28:
- ``ClassificationRule``: a single rule with match conditions
- ``ClassificationEngine``: evaluates rules against text nodes with
  action-based precedence (BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS)

Per D-23: conditions are ANDed — roles AND (regex OR keywords) must
all match for the rule to fire.  Per D-24: action precedence is
evaluated by iterating action groups in priority order and returning
the first matching rule.
"""

from __future__ import annotations

import re
from typing import Any

from anonreq.models.classification import ClassificationAction

# Action evaluation order per D-24 (highest priority first)
ACTION_PRECEDENCE: list[ClassificationAction] = [
    "BLOCK",
    "ROUTE_LOCAL",
    "ANONYMIZE",
    "PASS",
]


class ClassificationRule:
    """A single classification rule loaded from YAML.

    Attributes:
        id: Stable unique rule identifier (D-22).
        enabled: Whether the rule is active. Disabled rules are skipped.
        version: Integer version for audit trail (D-27).
        name: Human-readable name.
        action: The action to take when this rule matches.
        metadata: Arbitrary key-value metadata (owner, category, severity).
        roles: Message roles to match. Empty list = all roles.
        regex_patterns: List of regex patterns (matched case-insensitively).
        keywords: List of lowercase keywords for case-insensitive matching.
    """

    def __init__(
        self,
        id: str,
        enabled: bool = True,
        version: int = 1,
        name: str = "",
        action: ClassificationAction = "ANONYMIZE",
        metadata: dict[str, Any] | None = None,
        roles: list[str] | None = None,
        regex_patterns: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> None:
        self.id = id
        self.enabled = enabled
        self.version = version
        self.name = name
        self.action = action
        self.metadata = metadata or {}
        self.roles = roles or []

        # Pre-compile regex patterns with IGNORECASE
        self._compiled_patterns = (
            [re.compile(p, re.IGNORECASE) for p in regex_patterns]
            if regex_patterns
            else []
        )

        # Lowercase keywords for case-insensitive matching
        self._keywords = [kw.lower() for kw in keywords] if keywords else []

    def matches(self, text_nodes: list[dict[str, str]]) -> bool:
        """Check if this rule matches any of the given text nodes.

        Per D-23: conditions are ANDed — the node's role must match
        the rule's roles filter AND (any regex pattern OR any keyword)
        must match the node's value.

        Args:
            text_nodes: List of dicts with ``path``, ``role``, ``value`` keys.

        Returns:
            ``True`` if this rule matches at least one text node, ``False``
            if disabled or no text node matches.
        """
        if not self.enabled:
            return False

        for node in text_nodes:
            role = node.get("role", "")
            value = node.get("value", "")

            # Role filter: if roles is non-empty, node role must be in the list
            if self.roles and role not in self.roles:
                continue

            # If both regex and keywords are empty, match on roles alone
            if not self._compiled_patterns and not self._keywords:
                return True

            # Check regex patterns (ANY match)
            regex_match = any(
                pattern.search(value) for pattern in self._compiled_patterns
            )

            # Check keywords (ANY match, case-insensitive)
            value_lower = value.lower()
            keyword_match = any(kw in value_lower for kw in self._keywords)

            # Conditions are OR'd within: (regex OR keywords)
            if regex_match or keyword_match:
                return True

        return False


class ClassificationEngine:
    """Evaluates classification rules against text nodes.

    Per D-24: evaluates rules in action-priority order
    (BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS) and returns the first
    matching rule's action.

    Per D-27: records ``matched_rule_ids`` and ``matched_rule_versions``
    for auditability.

    Per D-28: ``default_action`` defines what to return when no rules
    match (typically ``"PASS"``).
    """

    def __init__(
        self,
        rules: list[ClassificationRule],
        default_action: ClassificationAction = "PASS",
    ) -> None:
        # Group rules by action for precedence-based evaluation
        self._rules_by_action: dict[ClassificationAction, list[ClassificationRule]] = {
            action: [] for action in ACTION_PRECEDENCE
        }
        for rule in rules:
            if rule.action in self._rules_by_action:
                self._rules_by_action[rule.action].append(rule)

        self._default_action = default_action

    def classify(self, text_nodes: list[dict[str, str]]) -> dict[str, Any]:
        """Classify text nodes by evaluating rules in precedence order.

        Args:
            text_nodes: List of TextNode dicts (path, role, value).

        Returns:
            Dict with:
            - ``action``: The winning action (first matching rule's action,
              or ``default_action`` if no match).
            - ``matched_rule_ids``: List of rule IDs that matched (typically
              one, but includes the first matching rule).
            - ``matched_rule_versions``: Corresponding versions for each
              matched rule ID.
        """
        for action in ACTION_PRECEDENCE:
            for rule in self._rules_by_action.get(action, []):
                if rule.matches(text_nodes):
                    return {
                        "action": action,
                        "matched_rule_ids": [rule.id],
                        "matched_rule_versions": [rule.version],
                    }

        return {
            "action": self._default_action,
            "matched_rule_ids": [],
            "matched_rule_versions": [],
        }
