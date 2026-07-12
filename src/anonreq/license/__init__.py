"""Licensing package exposing validator, configuration, and routing."""

from __future__ import annotations

from anonreq.license.config import LicenseSettings, license_settings
from anonreq.license.models import FeatureGate, LicenseKey, LicenseStatus, LicenseTier
from anonreq.license.router import router
from anonreq.license.validator import LicenseValidator, require_license

__all__ = [
    "FeatureGate",
    "LicenseKey",
    "LicenseStatus",
    "LicenseTier",
    "LicenseSettings",
    "license_settings",
    "LicenseValidator",
    "require_license",
    "router",
]
