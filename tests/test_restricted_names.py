"""Tests for RestrictedNamesManager — tenant restricted-names list with hot-reload.

Phase 15 Financial Services Compliance, D-002.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from anonreq.config.restricted_names import RestrictedNamesManager

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_yaml(tmp_path: Path) -> str:
    """Create a temporary restricted_names.yaml with sample data."""
    data = {
        "tenants": {
            "acme-corp": {
                "restricted_names": [
                    "Acme Merger Target Alpha",
                    "Project Firestorm",
                    "Unicorn Acquisition",
                ],
            },
            "bigbank": {
                "restricted_names": [
                    "Mercury Deal",
                    "Jupiter Partnership",
                ],
            },
            "empty-tenant": {
                "restricted_names": [],
            },
        },
    }
    path = tmp_path / "restricted_names.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return str(path)


@pytest.fixture
def manager(sample_yaml: str) -> RestrictedNamesManager:
    """Return a RestrictedNamesManager backed by the sample YAML."""
    return RestrictedNamesManager(config_path=sample_yaml)


# ── Test 1: Load restricted names from YAML for specific tenant ──────────────


class TestLoadRestrictedNames:
    """Loading restricted names from YAML configuration."""

    def test_load_returns_dict(self, manager: RestrictedNamesManager):
        """Loaded data is a dict keyed on tenant_id."""
        data = manager.load()
        assert isinstance(data, dict)
        assert "acme-corp" in data
        assert "bigbank" in data

    def test_acme_corp_has_three_names(self, manager: RestrictedNamesManager):
        """acme-corp tenant has 3 restricted names."""
        names = manager.get_names("acme-corp")
        assert len(names) == 3
        assert "Acme Merger Target Alpha" in names
        assert "Project Firestorm" in names
        assert "Unicorn Acquisition" in names

    def test_bigbank_has_two_names(self, manager: RestrictedNamesManager):
        """bigbank tenant has 2 restricted names."""
        names = manager.get_names("bigbank")
        assert len(names) == 2
        assert "Mercury Deal" in names
        assert "Jupiter Partnership" in names


# ── Test 2: Empty tenant returns empty list ──────────────────────────────────


class TestEmptyTenant:
    """Edge cases for tenants without restricted names."""

    def test_empty_tenant_returns_empty_list(self, manager: RestrictedNamesManager):
        """A tenant with no restricted names returns an empty list."""
        names = manager.get_names("empty-tenant")
        assert names == []

    def test_unknown_tenant_returns_empty_list(self, manager: RestrictedNamesManager):
        """A tenant not in the config returns an empty list (no crash)."""
        names = manager.get_names("nonexistent-tenant")
        assert names == []

    def test_no_argument_returns_empty_list(self, manager: RestrictedNamesManager):
        """Calling get_names with empty string returns empty list."""
        names = manager.get_names("")
        assert names == []


# ── Test 3: Names are case-insensitive matched ───────────────────────────────


class TestCaseInsensitiveMatching:
    """Restricted name matching is case-insensitive."""

    def test_exact_case_match(self, manager: RestrictedNamesManager):
        """Exact case match returns True."""
        assert manager.check_name("bigbank", "Mercury Deal") is True

    def test_lowercase_match(self, manager: RestrictedNamesManager):
        """Lowercase input matches uppercase name."""
        assert manager.check_name("bigbank", "mercury deal") is True

    def test_mixed_case_match(self, manager: RestrictedNamesManager):
        """Mixed-case input matches."""
        assert manager.check_name("acme-corp", "pRoJeCt FiReStOrM") is True

    def test_no_match_returns_false(self, manager: RestrictedNamesManager):
        """Non-matching text returns False."""
        assert manager.check_name("bigbank", "Nonexistent Name") is False

    def test_partial_word_match(self, manager: RestrictedNamesManager):
        """Partial word match within a restricted name returns True."""
        # 'Mercury' is part of 'Mercury Deal'
        assert manager.check_name("bigbank", "mercury") is True

    def test_substring_no_match(self, manager: RestrictedNamesManager):
        """Text that does not match any restricted name returns False."""
        assert manager.check_name("bigbank", "xyzzy") is False


# ── Test 4: Hot-reload picks up YAML changes without restart ─────────────────


class TestHotReload:
    """Hot-reload detects file changes and reloads data."""

    def test_reload_returns_false_when_unchanged(self, sample_yaml: str):
        """reload() returns False when file hasn't changed."""
        mgr = RestrictedNamesManager(config_path=sample_yaml)
        # Initial load already happened in __init__
        assert mgr.reload() is False

    def test_reload_detects_new_names(self, sample_yaml: str):
        """After modifying the YAML, reload() detects change and returns True."""
        mgr = RestrictedNamesManager(config_path=sample_yaml)
        initial = mgr.get_names("bigbank")
        assert len(initial) == 2

        # Ensure mtime will differ
        time.sleep(0.02)

        # Append a new name
        with open(sample_yaml) as f:
            data = yaml.safe_load(f)
        data["tenants"]["bigbank"]["restricted_names"].append("Platinum Venture")
        with open(sample_yaml, "w") as f:
            yaml.dump(data, f)

        assert mgr.reload() is True
        updated = mgr.get_names("bigbank")
        assert len(updated) == 3
        assert "Platinum Venture" in updated

    def test_reload_removes_deleted_names(self, sample_yaml: str):
        """After removing names from YAML, reload() reflects deletions."""
        mgr = RestrictedNamesManager(config_path=sample_yaml)
        assert len(mgr.get_names("acme-corp")) == 3

        time.sleep(0.02)

        # Remove one name
        with open(sample_yaml) as f:
            data = yaml.safe_load(f)
        data["tenants"]["acme-corp"]["restricted_names"].remove("Project Firestorm")
        with open(sample_yaml, "w") as f:
            yaml.dump(data, f)

        assert mgr.reload() is True
        updated = mgr.get_names("acme-corp")
        assert len(updated) == 2
        assert "Project Firestorm" not in updated

    def test_reload_detects_new_tenant(self, sample_yaml: str):
        """Adding a new tenant via YAML update is reflected after reload."""
        mgr = RestrictedNamesManager(config_path=sample_yaml)
        assert mgr.get_names("newco") == []

        time.sleep(0.02)

        with open(sample_yaml) as f:
            data = yaml.safe_load(f)
        data["tenants"]["newco"] = {"restricted_names": ["Secret Alpha"]}
        with open(sample_yaml, "w") as f:
            yaml.dump(data, f)

        assert mgr.reload() is True
        assert mgr.get_names("newco") == ["Secret Alpha"]

    def test_reload_noop_on_missing_file(self):
        """reload() does not crash when config file does not exist."""
        mgr = RestrictedNamesManager(config_path="/tmp/nonexistent_xyz.yaml")
        # Should not raise
        assert mgr.reload() is False
        assert mgr.get_names("any") == []


# ── Test 5: Constructor loads initial data ────────────────────────────────────


class TestConstructor:
    """Constructor behavior and edge cases."""

    def test_default_config_path(self):
        """Default config path is config/restricted_names.yaml."""
        mgr = RestrictedNamesManager()
        assert mgr.config_path.endswith("config/restricted_names.yaml")
        # May not exist in test env; that's OK
        _ = mgr.get_names("default")

    def test_no_crash_on_missing_file(self):
        """Creating manager with missing file does not crash."""
        mgr = RestrictedNamesManager(config_path="/tmp/does_not_exist.yaml")
        assert mgr.get_names("any") == []

    def test_corrupt_yaml_returns_empty(self, tmp_path: Path):
        """Corrupt YAML file yields empty data (no crash)."""
        path = tmp_path / "bad.yaml"
        path.write_text("{bad yaml: unclosed: [")
        mgr = RestrictedNamesManager(config_path=str(path))
        assert mgr.load() == {}
        assert mgr.get_names("tenant") == []


# ── Test 6: Thread safety ─────────────────────────────────────────────────────


class TestThreadSafety:
    """Concurrent reload safety."""

    def test_concurrent_reload_does_not_crash(self, sample_yaml: str):
        """Calling get_names() while reload() runs does not crash."""
        import threading

        mgr = RestrictedNamesManager(config_path=sample_yaml)
        results: list[Exception] = []

        def reload_loop():
            for _ in range(10):
                mgr.reload()

        def read_loop():
            for _ in range(50):
                try:
                    mgr.get_names("acme-corp")
                    mgr.check_name("acme-corp", "Project Firestorm")
                except Exception as e:
                    results.append(e)

        threads = [
            threading.Thread(target=reload_loop),
            threading.Thread(target=read_loop),
            threading.Thread(target=read_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 0, f"Concurrent access errors: {results}"

    def test_reload_under_lock(self, sample_yaml: str):
        """reload() acquires lock and does not leave stale state."""
        mgr = RestrictedNamesManager(config_path=sample_yaml)

        time.sleep(0.02)
        with open(sample_yaml) as f:
            data = yaml.safe_load(f)
        data["tenants"]["bigbank"]["restricted_names"] = ["New Mega Deal"]
        with open(sample_yaml, "w") as f:
            yaml.dump(data, f)

        mgr.reload()
        assert mgr.get_names("bigbank") == ["New Mega Deal"]
