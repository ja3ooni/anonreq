from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from anonreq.firewall.models import DetectionCategory, FirewallRule
from anonreq.firewall.reloader import FirewallRuleReloader
from anonreq.firewall.rules import FirewallRuleLoader


def _make_rule_dict(rule_id: str, category: str = "prompt_injection") -> dict:
    return {
        "rule_id": rule_id,
        "category": category,
        "pattern": r"(?i)(test)",
        "action": "BLOCK",
        "severity": "HIGH",
        "priority": 100,
    }


def _make_rules_yaml(rules: list[dict]) -> str:
    data = {
        "version": "1.0",
        "rules": rules,
        "category_config": {
            "prompt_injection": {"enabled": True, "threshold": 0.5},
        },
        "severity_mapping": {"high": "BLOCK", "medium": "FLAG_AND_FORWARD", "low": "MONITOR"},
    }
    return yaml.dump(data)


@pytest.fixture
def rules_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(_make_rules_yaml([_make_rule_dict("rule_001")]))
        path = f.name
    yield path
    os.unlink(path)


class TestFirewallRuleReloader:
    @pytest.mark.asyncio
    async def test_reload_atomically_replaces_rules(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)
        old, new = await rel.reload()
        assert isinstance(old, list)
        assert isinstance(new, list)
        assert len(new) >= 1
        assert new[0].rule_id == "rule_001"

    @pytest.mark.asyncio
    async def test_reload_returns_old_and_new_rules(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)
        old, new = await rel.reload()
        assert len(old) == 1
        assert len(new) == 1

    @pytest.mark.asyncio
    async def test_reload_after_file_change(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)

        old1, new1 = await rel.reload()
        assert len(new1) == 1

        with open(rules_file, "w") as f:
            f.write(_make_rules_yaml([
                _make_rule_dict("rule_001"),
                _make_rule_dict("rule_002", category="jailbreak"),
            ]))

        old2, new2 = await rel.reload()
        assert len(old2) == 1
        assert len(new2) == 2

    @pytest.mark.asyncio
    async def test_invalid_file_preserves_existing_rules(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)

        _, new1 = await rel.reload()
        assert len(new1) == 1

        with open(rules_file, "w") as f:
            f.write("invalid: yaml: [unbalanced")

        with patch.object(rel._logger, "error") as mock_error:
            old2, new2 = await rel.reload()
            assert len(old2) == 1
            assert len(new2) == 1
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_reloads_in_succession(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)

        for i in range(3):
            old, new = await rel.reload()
            assert len(new) >= 1

    @pytest.mark.asyncio
    async def test_watcher_start_stop_lifecycle(self, rules_file):
        loader = FirewallRuleLoader(path=rules_file)
        loader.load()
        rel = FirewallRuleReloader(loader)

        task = asyncio.create_task(rel.start_watcher(interval=0.1))
        await asyncio.sleep(0.05)
        assert rel._watcher_task is not None
        await rel.stop_watcher()
        assert task.done() or task.cancelled()
