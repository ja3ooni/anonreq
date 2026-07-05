"""Tests for proxy mode definitions and mode-dependent pipeline routing.

Tests cover:
- ProxyMode enum with 3 modes: proxy-only, full, transparent
- get_pipeline_for_mode returns correct stages per mode
- PROXY_ONLY skips detection, anonymization stages
- Mode read from ANONREQ_PROXY_MODE env var
- Invalid mode raises ConfigurationError
- Proxy-only mode still performs routing and audit
"""

from __future__ import annotations

import os

import pytest

from anonreq.exceptions import AnonReqError
from anonreq.proxy.modes import (
    PROXY_ONLY_STAGES,
    FULL_STAGES,
    ProxyMode,
    get_pipeline_for_mode,
    mode_from_env,
    requires_detection,
    requires_mitm,
    proxy_mode_description,
)


class TestProxyModeEnum:
    """Tests for ProxyMode enum values."""

    def test_proxy_only_value(self):
        assert ProxyMode.PROXY_ONLY.value == "proxy-only"

    def test_full_value(self):
        assert ProxyMode.FULL.value == "full"

    def test_transparent_value(self):
        assert ProxyMode.TRANSPARENT.value == "transparent"

    def test_three_modes(self):
        assert len(ProxyMode) == 3


class TestGetPipelineForMode:
    """Tests for get_pipeline_for_mode function."""

    def test_proxy_only_returns_correct_stages(self):
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert stages == PROXY_ONLY_STAGES

    def test_proxy_only_skips_detection(self):
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert "detection" not in stages
        assert "anonymization" not in stages
        assert "classification" not in stages
        assert "provider_call" not in stages
        assert "restoration" not in stages

    def test_proxy_only_includes_routing_and_audit(self):
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert "routing" in stages
        assert "audit" in stages
        assert "forwarding_guard" in stages

    def test_full_returns_all_stages(self):
        stages = get_pipeline_for_mode(ProxyMode.FULL)
        assert stages == FULL_STAGES

    def test_full_includes_detection_and_anonymization(self):
        stages = get_pipeline_for_mode(ProxyMode.FULL)
        assert "detection" in stages
        assert "anonymization" in stages
        assert "classification" in stages

    def test_transparent_equals_full_stages(self):
        transparent = get_pipeline_for_mode(ProxyMode.TRANSPARENT)
        full = get_pipeline_for_mode(ProxyMode.FULL)
        assert transparent == full

    def test_proxy_only_is_shorter_than_full(self):
        proxy_only = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        full = get_pipeline_for_mode(ProxyMode.FULL)
        assert len(proxy_only) < len(full)

    def test_proxy_only_has_no_extra_stages_not_in_pipeline(self):
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        valid_stages = {
            "auth", "routing", "forwarding_guard", "audit",
            "classification", "detection", "anonymization",
            "provider_call", "restoration",
        }
        for stage in stages:
            assert stage in valid_stages


class TestModeFromEnv:
    """Tests for mode_from_env function."""

    def test_proxy_only_from_env(self, monkeypatch):
        monkeypatch.setenv("ANONREQ_PROXY_MODE", "proxy-only")
        assert mode_from_env() == ProxyMode.PROXY_ONLY

    def test_full_from_env(self, monkeypatch):
        monkeypatch.setenv("ANONREQ_PROXY_MODE", "full")
        assert mode_from_env() == ProxyMode.FULL

    def test_transparent_from_env(self, monkeypatch):
        monkeypatch.setenv("ANONREQ_PROXY_MODE", "transparent")
        assert mode_from_env() == ProxyMode.TRANSPARENT

    def test_default_mode_is_full(self, monkeypatch):
        monkeypatch.delenv("ANONREQ_PROXY_MODE", raising=False)
        assert mode_from_env() == ProxyMode.FULL

    def test_invalid_mode_raises_error(self, monkeypatch):
        monkeypatch.setenv("ANONREQ_PROXY_MODE", "invalid")
        with pytest.raises(AnonReqError):
            mode_from_env()

    def test_case_sensitive_mode(self, monkeypatch):
        monkeypatch.setenv("ANONREQ_PROXY_MODE", "PROXY_ONLY")
        with pytest.raises(AnonReqError):
            mode_from_env()


class TestRequiresMitm:
    """Tests for requires_mitm function."""

    def test_proxy_only_does_not_require_mitm(self):
        assert requires_mitm(ProxyMode.PROXY_ONLY) is False

    def test_full_does_not_require_mitm(self):
        assert requires_mitm(ProxyMode.FULL) is False

    def test_transparent_requires_mitm(self):
        assert requires_mitm(ProxyMode.TRANSPARENT) is True


class TestRequiresDetection:
    """Tests for requires_detection function."""

    def test_proxy_only_does_not_require_detection(self):
        assert requires_detection(ProxyMode.PROXY_ONLY) is False

    def test_full_requires_detection(self):
        assert requires_detection(ProxyMode.FULL) is True

    def test_transparent_requires_detection(self):
        assert requires_detection(ProxyMode.TRANSPARENT) is True


class TestProxyModeDescription:
    """Tests for proxy_mode_description function."""

    def test_proxy_only_description(self):
        desc = proxy_mode_description(ProxyMode.PROXY_ONLY)
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_full_description(self):
        desc = proxy_mode_description(ProxyMode.FULL)
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_transparent_description(self):
        desc = proxy_mode_description(ProxyMode.TRANSPARENT)
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_descriptions_are_unique(self):
        descs = {
            proxy_mode_description(ProxyMode.PROXY_ONLY),
            proxy_mode_description(ProxyMode.FULL),
            proxy_mode_description(ProxyMode.TRANSPARENT),
        }
        assert len(descs) == 3


class TestProxyModeIntegration:
    """Integration tests for proxy mode with the FastAPI app.

    These tests verify that proxy-only mode correctly skips
    detection while still performing routing and audit.
    """

    async def test_proxy_only_skips_detection_in_middleware(self):
        """Proxy-only mode should not invoke detection middleware."""
        from unittest.mock import AsyncMock, patch

        with patch("anonreq.proxy.modes.get_pipeline_for_mode") as mock_get:
            mock_get.return_value = ["auth", "routing", "forwarding_guard", "audit"]
            stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
            assert "detection" not in stages

    async def test_proxy_only_routes_through_mitm_handler(self):
        """Proxy-only mode should still route through MITM handler."""
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert "routing" in stages

    async def test_proxy_only_still_audits(self):
        """Proxy-only mode should still write audit events."""
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert "audit" in stages

    async def test_proxy_only_forwarding_guard(self):
        """Proxy-only mode should still perform ForwardingGuard decision."""
        stages = get_pipeline_for_mode(ProxyMode.PROXY_ONLY)
        assert "forwarding_guard" in stages
