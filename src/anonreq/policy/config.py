from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, model_validator

from anonreq.policy.models import PolicyAction, PolicyRule, RateLimitConfig, ResidencyRule, SpendBudget


class PolicyConfig(BaseModel):
    model_config = {"extra": "forbid"}

    version: str
    tenant_id: str | None = None
    rules: list[PolicyRule]
    rate_limits: RateLimitConfig | None = None
    spend_budgets: dict[str, SpendBudget] = {}
    residency_rules: dict[str, ResidencyRule] = {}
    default_action: PolicyAction = PolicyAction.ALLOW

    @model_validator(mode="before")
    @classmethod
    def _coerce_rules(cls, data: Any) -> Any:
        if isinstance(data, dict) and "rules" in data:
            rules = data["rules"]
            if rules is None:
                data["rules"] = []
        return data


policy_config: PolicyConfig | None = None


def load_policy_config(path: str | Path = "config/policy.yaml") -> PolicyConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Policy configuration file not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {"version": "1.0", "rules": []}
    return PolicyConfig.model_validate(raw)


def validate_policy_bundle(config: PolicyConfig) -> list[str]:
    warnings: list[str] = []

    rule_ids = [r.rule_id for r in config.rules]
    duplicates = [rid for rid, count in Counter(rule_ids).items() if count > 1]
    for dup in duplicates:
        warnings.append(f"Duplicate rule_id '{dup}' found in policy configuration")

    priorities = [(r.rule_id, r.priority) for r in config.rules]
    priority_map: dict[int, list[str]] = {}
    for rid, pri in priorities:
        priority_map.setdefault(pri, []).append(rid)
    for pri, rids in priority_map.items():
        if len(rids) > 1:
            warnings.append(f"Conflicting priority {pri} for rules: {', '.join(rids)}")

    enabled_count = sum(1 for r in config.rules if r.enabled)
    if enabled_count == 0:
        warnings.append("No enabled rules in policy configuration — all forwarding may be affected")

    return warnings
