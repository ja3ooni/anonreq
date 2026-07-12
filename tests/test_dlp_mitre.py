"""Unit tests for MITRE ATT&CK mapping config and lookup (Plan 13-04, Task 1).

Tests cover:
- MITRE mapping config loads correctly from YAML
- Each DLP category returns correct technique ID
- Default fallback for unknown categories
- Config version and structure validation
"""

from __future__ import annotations

import pytest
import yaml

MITRE_CONFIG_PATH = "config/mitre_attack.yaml"


@pytest.fixture
def mitre_config():
    with open(MITRE_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    return data["mitre_attack"]


def test_mitre_config_loads():
    """MITRE ATT&CK config loads safely from YAML."""
    with open(MITRE_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    assert "mitre_attack" in data
    assert data["mitre_attack"]["version"] == "15.1"


def test_mitre_config_has_all_categories(mitre_config):
    """All 8 DLP core categories + exfiltration + default are mapped."""
    mappings = mitre_config["mappings"]
    expected_categories = {
        "PII",
        "Financial",
        "Health",
        "Source Code",
        "Credentials",
        "Legal",
        "Export Controlled",
        "Intellectual Property",
        "Exfiltration",
    }
    for cat in expected_categories:
        assert cat in mappings, f"Missing MITRE mapping for {cat}"
    assert "default" in mitre_config


def test_mitre_technique_ids_present(mitre_config):
    """Each mapping entry has technique_id and technique_name."""
    for category, mapping in mitre_config["mappings"].items():
        if category == "default":
            continue
        assert "technique_id" in mapping, f"{category} missing technique_id"
        assert "technique_name" in mapping, f"{category} missing technique_name"
        assert mapping["technique_id"], f"{category} has empty technique_id"


def test_mitre_pii_technique_id(mitre_config):
    """PII category maps to T1048.002 (Exfiltration Over Alternative Protocol)."""
    assert mitre_config["mappings"]["PII"]["technique_id"] == "T1048.002"


def test_mitre_exfiltration_technique_id(mitre_config):
    """Exfiltration category maps to T1048."""
    assert mitre_config["mappings"]["Exfiltration"]["technique_id"] == "T1048"


def test_mitre_credentials_technique_id(mitre_config):
    """Credentials category maps to T1552 (Unsecured Credentials)."""
    assert mitre_config["mappings"]["Credentials"]["technique_id"] == "T1552"


def test_mitre_source_code_technique_id(mitre_config):
    """Source Code category maps to T1567.002."""
    assert mitre_config["mappings"]["Source Code"]["technique_id"] == "T1567.002"


def test_mitre_export_controlled_technique_id(mitre_config):
    """Export Controlled maps to T1048.003."""
    assert mitre_config["mappings"]["Export Controlled"]["technique_id"] == "T1048.003"


def test_mitre_default_fallback(mitre_config):
    """Default mapping exists for unknown categories."""
    default = mitre_config.get("default", {})
    assert "technique_id" in default
    assert default["technique_id"] == "T1048"


def test_mitre_mappings_have_tactics(mitre_config):
    """Each mapping (except default) has a tactics list."""
    for category, mapping in mitre_config["mappings"].items():
        if category == "default":
            continue
        assert "tactics" in mapping, f"{category} missing tactics"
        assert isinstance(mapping["tactics"], list), f"{category} tactics not a list"
        assert len(mapping["tactics"]) >= 1, f"{category} has empty tactics"


def test_mitre_ip_technique_id(mitre_config):
    """Intellectual Property maps to T1567.002."""
    ip_mapping = mitre_config["mappings"]["Intellectual Property"]
    assert ip_mapping["technique_id"] == "T1567.002"


def test_mitre_config_min_entries():
    """MITRE config has at least 9 category entries (8 core + exfiltration + default)."""
    with open(MITRE_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    mappings = data["mitre_attack"]["mappings"]
    assert len(mappings) >= 9
