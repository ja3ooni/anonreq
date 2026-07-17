"""Unit tests for canonical RBAC role normalization."""

from __future__ import annotations

from anonreq.middleware.rbac import Role, _normalize_role_value


def test_read_only_alias_maps_to_enterprise_role():
    assert Role.READ_ONLY.value == "read_only_auditor"
    assert Role.READ_ONLY_AUDITOR.value == "read_only_auditor"
    assert Role("read_only_auditor") is Role.READ_ONLY_AUDITOR


def test_legacy_read_only_role_normalizes_to_canonical_value():
    assert _normalize_role_value("read_only") == "read_only_auditor"
    assert _normalize_role_value("read_only_auditor") == "read_only_auditor"
    assert _normalize_role_value("operator") == "operator"
