from __future__ import annotations

from fastapi import APIRouter, HTTPException

from anonreq.firewall.models import DetectionCategory
from anonreq.firewall.rules import FirewallRuleLoader, load_firewall_rules

router = APIRouter()
_loader: FirewallRuleLoader | None = None


def _get_loader() -> FirewallRuleLoader:
    global _loader
    if _loader is None:
        _loader = FirewallRuleLoader()
        _loader.load()
    return _loader


@router.get("/v1/admin/prompt-security/rules")
async def list_firewall_rules(
    category: str | None = None,
    enabled: bool | None = None,
):
    loader = _get_loader()
    rules = loader.rules

    if category:
        try:
            cat = DetectionCategory(category)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid category: {category}")
        rules = [r for r in rules if r.category == cat]

    if enabled is not None:
        rules = [r for r in rules if r.enabled == enabled]

    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "category": r.category.value,
                "action": r.action.value,
                "enabled": r.enabled,
                "severity": r.severity.value,
                "priority": r.priority,
                "description": r.description,
            }
            for r in rules
        ],
        "category_config": {
            k: v.model_dump() for k, v in loader.category_config.items()
        },
        "severity_mapping": loader.severity_mapping.model_dump(),
        "total_rules": len(loader.rules),
        "enabled_rules": len([r for r in loader.rules if r.enabled]),
        "version": "1.0",
    }


@router.get("/v1/admin/prompt-security/rules/{rule_id}")
async def get_firewall_rule(rule_id: str):
    loader = _get_loader()
    for rule in loader.rules:
        if rule.rule_id == rule_id:
            return {
                "rule_id": rule.rule_id,
                "category": rule.category.value,
                "action": rule.action.value,
                "enabled": rule.enabled,
                "severity": rule.severity.value,
                "priority": rule.priority,
                "description": rule.description,
                "pattern": rule.pattern,
            }
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
