"""Unit tests for LicenseSettings environment variable configuration."""

from __future__ import annotations

import os
import pytest
from anonreq.license.config import LicenseSettings


def test_default_license_settings():
    """Verify default configurations are None."""
    # Ensure env is clear
    original_secret = os.environ.pop("ANONREQ_LICENSE_SECRET", None)
    original_key = os.environ.pop("ANONREQ_LICENSE_KEY", None)

    try:
        settings = LicenseSettings()
        assert settings.LICENSE_SECRET is None
        assert settings.LICENSE_KEY is None
    finally:
        # Restore env
        if original_secret is not None:
            os.environ["ANONREQ_LICENSE_SECRET"] = original_secret
        if original_key is not None:
            os.environ["ANONREQ_LICENSE_KEY"] = original_key


def test_license_secret_from_env(monkeypatch):
    """Verify LICENSE_SECRET is read correctly from environment."""
    monkeypatch.setenv("ANONREQ_LICENSE_SECRET", "test-secret-value-123")
    settings = LicenseSettings()
    assert settings.LICENSE_SECRET == "test-secret-value-123"


def test_license_key_from_env(monkeypatch):
    """Verify LICENSE_KEY is read correctly from environment."""
    monkeypatch.setenv("ANONREQ_LICENSE_KEY", "test-key-value-abc")
    settings = LicenseSettings()
    assert settings.LICENSE_KEY == "test-key-value-abc"
