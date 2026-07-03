"""Test helpers for Phase 8 Enterprise Policy Engine tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from anonreq.policy.models import UsageRecord


def create_temp_policy_yaml(tmp_path: Path, overrides: dict[str, Any] | None = None) -> Path:
    """Create a temporary policy.yaml for config loading tests.

    Args:
        tmp_path: pytest tmp_path fixture value.
        overrides: Optional dict to merge into the default policy config.

    Returns:
        Path to the created YAML file.
    """
    default = {
        "version": "1.0",
        "rules": [
            {"rule_id": "test_rule", "name": "Test Rule", "action": "BLOCK", "priority": 50},
        ],
        "rate_limits": {"rpm": 1000, "tpm": 100000, "concurrent": 50, "enabled": True},
        "spend_budgets": {},
        "residency_rules": {},
    }
    if overrides:
        _deep_merge(default, overrides)
    path = tmp_path / "policy.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(default, f)
    return path


def sample_usage_record(tenant_id: str = "test_tenant") -> UsageRecord:
    """Create a sample UsageRecord for test reuse.

    Args:
        tenant_id: Tenant identifier (default: ``"test_tenant"``).

    Returns:
        A UsageRecord with zero values and current timestamp.
    """
    return UsageRecord(
        tenant_id=tenant_id,
        rpm_current=0,
        tpm_current=0,
        concurrent_current=0,
        daily_spend=Decimal("0"),
        monthly_spend=Decimal("0"),
        reset_at=datetime.now(timezone.utc),
    )


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge overrides into base dict."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
