from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from anonreq.firewall.models import (
    DetectionCategory,
    FirewallRule,
    RuleCategoryConfig,
    SeverityActionMapping,
)


class FirewallRuleLoader:
    def __init__(self, path: str = "config/prompt-security-rules.yaml") -> None:
        self._path = path
        self._rules: list[FirewallRule] = []
        self._category_config: dict[str, RuleCategoryConfig] = {}
        self._severity_mapping: SeverityActionMapping = SeverityActionMapping()

    def load(self) -> list[FirewallRule]:
        path = Path(self._path)
        if not path.exists():
            return []
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        raw_rules: list[dict[str, Any]] = data.get("rules", [])
        parsed: list[FirewallRule] = []
        seen: set[str] = set()

        for raw in raw_rules:
            rule = FirewallRule(**raw)
            if rule.rule_id in seen:
                # Last wins for hot-reload deduplication
                parsed = [r for r in parsed if r.rule_id != rule.rule_id]
            parsed.append(rule)
            seen.add(rule.rule_id)

        self._parse_category_config(data.get("category_config", {}))
        self._parse_severity_mapping(data.get("severity_mapping", {}))

        self._rules = parsed
        return list(self._rules)

    def reload(self) -> list[FirewallRule]:
        return self.load()

    def get_rules_by_category(self, category: DetectionCategory) -> list[FirewallRule]:
        return [r for r in self._rules if r.category == category]

    @property
    def rules(self) -> list[FirewallRule]:
        return list(self._rules)

    @property
    def category_config(self) -> dict[str, RuleCategoryConfig]:
        return dict(self._category_config)

    @property
    def severity_mapping(self) -> SeverityActionMapping:
        return self._severity_mapping

    def _parse_category_config(self, raw: dict[str, Any]) -> None:
        self._category_config = {}
        for key, value in raw.items():
            if isinstance(value, dict):
                self._category_config[key] = RuleCategoryConfig(**value)
            else:
                self._category_config[key] = RuleCategoryConfig()

    def _parse_severity_mapping(self, raw: dict[str, Any]) -> None:
        if raw:
            self._severity_mapping = SeverityActionMapping(**raw)


def load_firewall_rules(path: str = "config/prompt-security-rules.yaml") -> list[FirewallRule]:
    loader = FirewallRuleLoader(path)
    return loader.load()
