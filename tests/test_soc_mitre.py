"""Tests for SOC MITRE mapping loader and resolver.

Tests for:
- Loading valid YAML config
- Mapping entry validation (required fields)
- resolve() for known and unknown event types
- Invalid YAML handling
- Missing field handling
"""

from __future__ import annotations

import os
import tempfile

import pytest

from anonreq.soc.mitre import MITREMapper


def _write_temp_yaml(content: str) -> str:
    """Write YAML content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


class TestMITREMapperLoad:
    """Tests for MITREMapper YAML loading."""

    def test_load_valid_yaml(self):
        """Test 1: Load valid YAML with event_type_mappings."""
        yaml_content = """
event_type_mappings:
  test_event:
    mitre_id: T9999
    framework: ATT&CK
    technique: Test Technique
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            entry = mapper.get_entry("test_event")
            assert entry is not None
            assert entry.event_type == "test_event"
            assert entry.mitre_id == "T9999"
            assert entry.framework == "ATT&CK"
            assert entry.technique == "Test Technique"
        finally:
            os.unlink(path)

    def test_load_with_multiple_mappings(self):
        """Test that multiple mappings load correctly."""
        yaml_content = """
event_type_mappings:
  event_a:
    mitre_id: T1000
    framework: ATT&CK
    technique: Technique A
  event_b:
    mitre_id: T2000
    framework: ATLAS
    technique: Technique B
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            assert mapper.resolve("event_a") == "T1000"
            assert mapper.resolve("event_b") == "T2000"
        finally:
            os.unlink(path)

    def test_each_entry_has_required_fields(self):
        """Test 2: Each mapping entry has event_type, mitre_id, framework, technique."""
        yaml_content = """
event_type_mappings:
  valid_event:
    mitre_id: T9999
    framework: ATT&CK
    technique: Valid
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            entry = mapper.get_entry("valid_event")
            assert entry is not None
            assert hasattr(entry, "event_type")
            assert hasattr(entry, "mitre_id")
            assert hasattr(entry, "framework")
            assert hasattr(entry, "technique")
        finally:
            os.unlink(path)


class TestMITREMapperResolve:
    """Tests for MITREMapper.resolve()."""

    def test_resolve_known_event_type(self):
        """Test 3: resolve returns correct mitre_id for known event_type."""
        yaml_content = """
event_type_mappings:
  dlp_violation:
    mitre_id: T1048
    framework: ATT&CK
    technique: Exfiltration Over Alternative Protocol
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            assert mapper.resolve("dlp_violation") == "T1048"
        finally:
            os.unlink(path)

    def test_resolve_unknown_event_type_returns_temp_unmapped(self):
        """Test 4: resolve returns TEMP:UNMAPPED for unknown event_type."""
        yaml_content = """
event_type_mappings:
  known_event:
    mitre_id: T9999
    framework: ATT&CK
    technique: Known
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            assert mapper.resolve("unknown_event") == "TEMP:UNMAPPED"
        finally:
            os.unlink(path)

    def test_empty_mappings_returns_temp_unmapped(self):
        """resolve returns TEMP:UNMAPPED when no mappings exist."""
        yaml_content = "event_type_mappings: {}\n"
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            assert mapper.resolve("anything") == "TEMP:UNMAPPED"
        finally:
            os.unlink(path)


class TestMITREMapperErrors:
    """Tests for MITREMapper error handling."""

    def test_invalid_yaml_raises_error(self):
        """Test 5: Invalid YAML raises ConfigurationError."""
        path = _write_temp_yaml("invalid: yaml: [bad\n  broken")
        try:
            with pytest.raises(Exception):  # noqa: B017, PT011
                MITREMapper(path)
        finally:
            os.unlink(path)

    def test_missing_required_field_raises_validation_error(self):
        """Test 6: Missing required field raises validation error."""
        yaml_content = """
event_type_mappings:
  bad_event:
    mitre_id: T9999
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            errors = mapper.validate()
            assert len(errors) > 0
            assert any("bad_event" in err for err in errors)
        finally:
            os.unlink(path)

    def test_nonexistent_file_raises_error(self):
        """Non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            MITREMapper("/nonexistent/path/mitre.yaml")


class TestMITREMapperGetEntry:
    """Tests for MITREMapper.get_entry()."""

    def test_get_entry_known(self):
        """get_entry returns full MappingEntry for known event_type."""
        yaml_content = """
event_type_mappings:
  prompt_injection:
    mitre_id: T1566.001
    framework: ATT&CK
    technique: Spearphishing Attachment
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            entry = mapper.get_entry("prompt_injection")
            assert entry is not None
            assert entry.mitre_id == "T1566.001"
        finally:
            os.unlink(path)

    def test_get_entry_unknown(self):
        """get_entry returns None for unknown event_type."""
        yaml_content = """
event_type_mappings:
  known_event:
    mitre_id: T9999
    framework: ATT&CK
    technique: Known
"""
        path = _write_temp_yaml(yaml_content)
        try:
            mapper = MITREMapper(path)
            assert mapper.get_entry("unknown") is None
        finally:
            os.unlink(path)
