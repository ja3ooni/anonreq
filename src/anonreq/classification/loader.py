"""Classification rule loader — YAML loading and Pydantic validation.

Per D-22:
- Rules are loaded from a YAML file at startup
- ``yaml.safe_load()`` prevents arbitrary code execution (T-02-02-01)
- Pydantic validation rejects malformed rule structure
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from anonreq.classification.engine import ClassificationRule


class ClassificationRuleLoader:
    """Loads classification rules from YAML or Python dicts.

    Usage::

        rules = ClassificationRuleLoader.from_yaml("config/classification.yaml")
        engine = ClassificationEngine(rules)

    Or directly from a pre-parsed dict::

        rules = ClassificationRuleLoader.from_dict({"rules": [...]})
    """

    @staticmethod
    def from_yaml(path: str | Path) -> list[ClassificationRule]:
        """Load classification rules from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            List of ``ClassificationRule`` instances.

        Raises:
            ValueError: If the YAML structure is invalid (missing ``rules``
                key, or a rule missing required ``id`` or ``action`` fields).
            FileNotFoundError: If the file does not exist.
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "rules" not in data:
            raise ValueError(
                "YAML config must contain a 'rules' key at the top level"
            )

        return ClassificationRuleLoader.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> list[ClassificationRule]:
        """Load classification rules from a parsed dict.

        Args:
            data: Dict with a ``rules`` key containing a list of rule dicts.

        Returns:
            List of ``ClassificationRule`` instances.

        Raises:
            ValueError: If the dict structure is invalid.
        """
        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raise ValueError("'rules' must be a list")

        rules: list[ClassificationRule] = []
        for i, raw in enumerate(raw_rules):
            if not isinstance(raw, dict):
                raise ValueError(f"Rule at index {i} must be a dict")

            rule_id = raw.get("id")
            if not rule_id:
                raise ValueError(f"Rule at index {i} is missing required 'id' field")

            action = raw.get("action")
            if not action:
                raise ValueError(
                    f"Rule '{rule_id}' is missing required 'action' field"
                )

            conditions = raw.get("conditions", {})
            if not isinstance(conditions, dict):
                conditions = {}

            rules.append(
                ClassificationRule(
                    id=rule_id,
                    enabled=raw.get("enabled", True),
                    version=raw.get("version", 1),
                    name=raw.get("name", ""),
                    action=action,
                    metadata=raw.get("metadata", {}),
                    roles=conditions.get("roles", []),
                    regex_patterns=conditions.get("regex", []),
                    keywords=conditions.get("keywords", []),
                )
            )

        return rules
