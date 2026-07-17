"""License validator for HMAC-SHA256 commercial licensing.

Per GUARD-03:
- Validates ANONREQ_LICENSE_KEY using ANONREQ_LICENSE_SECRET key
- Caches verification status in memory for application lifetime
- require_license returns 402 detail on unlicensed feature access
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request

from anonreq.license.config import license_settings
from anonreq.license.models import FeatureGate, LicensePayload, LicenseStatus

logger = logging.getLogger(__name__)

# Module-level variable for in-memory caching of license status
_cached_status: LicenseStatus | None = None


class LicenseValidator:
    """Validator class for offline license key validation."""

    @classmethod
    async def get_status(cls) -> LicenseStatus:
        """Get cached license status or validate if not cached."""
        global _cached_status
        if _cached_status is not None:
            return _cached_status
        _cached_status = await cls.validate_license()
        return _cached_status

    @classmethod
    def invalidate_cache(cls) -> None:
        """Reset the cached license status."""
        global _cached_status
        _cached_status = None

    @classmethod
    async def validate_license(cls) -> LicenseStatus:
        """Validate the license key from the configuration settings."""
        key = license_settings.LICENSE_KEY
        secret = license_settings.LICENSE_SECRET

        if not key:
            return LicenseStatus(
                valid=False,
                message="No license key configured",
            )

        if not secret:
            return LicenseStatus(
                valid=False,
                message="No license secret configured",
            )

        try:
            # Decode the base64-encoded key payload
            decoded = base64.b64decode(key).decode("utf-8")
            if "." not in decoded:
                return LicenseStatus(
                    valid=False,
                    message="Invalid license key format",
                )

            data, signature_hex = decoded.rsplit(".", 1)

            # Recompute HMAC-SHA256 signature
            expected = hmac.new(
                secret.encode("utf-8"),
                data.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Compare signatures using constant-time comparison
            if not hmac.compare_digest(expected, signature_hex):
                return LicenseStatus(
                    valid=False,
                    message="Invalid license signature",
                )

            payload_dict = json.loads(data)
            payload = LicensePayload(**payload_dict)

            now = datetime.now(UTC)
            expires_at = payload.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(UTC)

            if now > expires_at:
                return LicenseStatus(
                    valid=False,
                    tier=payload.tier,
                    features=payload.features,
                    expires_at=payload.expires_at,
                    organization=payload.org,
                    message="License expired",
                )

            return LicenseStatus(
                valid=True,
                tier=payload.tier,
                features=payload.features,
                expires_at=payload.expires_at,
                organization=payload.org,
                message="License valid",
            )

        except Exception as exc:
            logger.error("Error during license validation: %s", exc)
            return LicenseStatus(
                valid=False,
                message=f"License validation failed: {exc!s}",
            )

    @classmethod
    async def check_feature(cls, feature: FeatureGate | str) -> bool:
        """Check if a given feature is currently licensed."""
        status = await cls.get_status()
        if not status.valid:
            return False

        feature_val = feature if isinstance(feature, str) else feature.value
        return any(f.value == feature_val for f in status.features)


def require_license(feature: FeatureGate | str) -> Any:
    """Dependency that gates access to endpoints requiring a valid license."""

    async def _check(request: Request) -> None:  # noqa: ARG001
        if not await LicenseValidator.check_feature(feature):
            feature_name = feature if isinstance(feature, str) else feature.value
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "license_required",
                    "feature": feature_name,
                    "message": "A valid Appliance-tier license is required for this feature",
                },
            )

    return _check
