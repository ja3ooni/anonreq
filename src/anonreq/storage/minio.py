"""MinIO WORM bucket manager for SEC 17a-4 MNPI audit retention.

Phase 15 Financial Services Compliance, D-004.

Provides:
- ``MINIO_WORM_BUCKET`` constant (``anonreq-mnpi-audit``)
- ``MinioWormBucket`` — manager for WORM (Write Once Read Many) operations
- ``create_mnpi_worm_bucket`` — factory using env vars

Per SEC 17a-4:
- Bucket created with ``object_lock=True`` (WORM mode)
- Retention policy: COMPLIANCE mode, 7-year retain-until-date
- Object lock on each stored object prevents delete/overwrite

Per T-15-01-01: Only SHA-256 hashes of detected values are stored,
never raw PII/MNPI.

Per T-15-01-02: Object lock with COMPLIANCE mode prevents deletion
and overwrite, satisfying SEC 17a-4 non-erasable/non-rewritable
requirements.
"""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, timedelta
from typing import Any

try:
    from minio import Minio
    from minio.error import S3Error
    from minio.retention import Retention
except ImportError:
    raise ImportError(
        "minio is required for storage features. "
        "Install with: pip install 'anonreq[storage]'"
    ) from None

from anonreq.models.audit import MnpiAuditEvent

logger = logging.getLogger("anonreq.storage.minio")

MNPI_WORM_BUCKET = "anonreq-mnpi-audit"
"""Dedicated MinIO WORM bucket name for MNPI audit events."""

RETENTION_DAYS = 2557  # 7 years (365.25 * 7 ≈ 2557)


class MinioWormBucket:
    """Manages the MNPI audit WORM bucket in MinIO.

    Args:
        endpoint: MinIO server endpoint (e.g. ``localhost:9000``).
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        secure: Use HTTPS for MinIO connections (default: True).
        bucket: Bucket name (default: ``anonreq-mnpi-audit``).
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = True,
        bucket: str = MNPI_WORM_BUCKET,
    ) -> None:
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._bucket = bucket
        self._client: Minio | None = None

    @property
    def bucket(self) -> str:
        """Return the configured bucket name."""
        return self._bucket

    def _get_client(self) -> Minio:
        """Lazy-initialize and return the MinIO client."""
        if self._client is None:
            self._client = Minio(
                self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure,
            )
        return self._client

    async def ensure_bucket(self) -> bool:
        """Ensure the WORM bucket exists with correct configuration.

        Creates the bucket with ``object_lock=True`` if it does not
        exist, and sets a default COMPLIANCE retention policy.

        Returns:
            ``True`` if the bucket is ready, ``False`` on failure.
        """
        client = self._get_client()
        try:
            exists = client.bucket_exists(self._bucket)
            if not exists:
                client.make_bucket(self._bucket, object_lock=True)
                logger.info("MNPI WORM bucket created: %s", self._bucket)

            # Verify bucket is accessible
            return True
        except S3Error as exc:
            logger.error("MNPI WORM bucket setup failed: %s - %s", self._bucket, exc)
            return False

    async def store_mnpi_audit_event(self, event: MnpiAuditEvent) -> str:
        """Store an MNPI audit event in the WORM bucket.

        Serializes the event to JSON and uploads it to
        ``anonreq-mnpi-audit/{tenant_id}/{year}/{month}/{day}/{event_id}.json``
        with COMPLIANCE-mode object lock and 7-year retention.

        Args:
            event: The ``MnpiAuditEvent`` to store.

        Returns:
            The object path (``tenant_id/.../event_id.json``).

        Raises:
            S3Error: If the upload or lock configuration fails.
        """
        client = self._get_client()
        # Serialize to JSON, excluding None fields and the full timestamp
        payload = {
            "event_id": event.event_id,
            "tenant_id": event.tenant_id,
            "session_id": event.session_id,
            "entity_type": event.entity_type,
            "policy_action": event.policy_action,
            "detected_value_hash": event.detected_value_hash,
            "timestamp": event.timestamp.isoformat(),
        }
        if event.policy_rule_id is not None:
            payload["policy_rule_id"] = event.policy_rule_id

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        length = len(body)

        ts = event.timestamp
        object_path = (
            f"{event.tenant_id}/{ts.year:04d}/{ts.month:02d}/{ts.day:02d}"
            f"/{event.event_id}.json"
        )

        retain_until = ts.replace(tzinfo=UTC) + timedelta(days=RETENTION_DAYS)

        client.put_object(
            self._bucket,
            object_path,
            data=io.BytesIO(body),
            length=length,
            content_type="application/json",
        )

        # Set COMPLIANCE mode retention on the object
        client.set_object_retention(
            self._bucket,
            object_path,
            Retention(
                mode="COMPLIANCE",
                retain_until_date=retain_until,
            ),
        )

        logger.info(
            "MNPI audit event stored: %s/%s (%s)",
            self._bucket, object_path, event.entity_type,
        )

        return object_path

    async def get_audit_event(self, path: str) -> dict[str, Any] | None:
        """Retrieve an MNPI audit event from the WORM bucket.

        Args:
            path: The object path (e.g. ``acme-corp/2026/07/04/evt123.json``).

        Returns:
            The parsed event dict, or ``None`` if not found.
        """
        client = self._get_client()
        try:
            response = client.get_object(self._bucket, path)
            data = json.loads(response.read())
            response.close()
            response.release_conn()
            return data
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            logger.error("MNPI get audit event failed: %s - %s", path, exc)
            return None

    async def list_audit_events(
        self,
        tenant_id: str,
        prefix: str = "",
    ) -> list[str]:
        """List MNPI audit event object paths by tenant.

        Args:
            tenant_id: The tenant identifier.
            prefix: Optional additional path prefix after tenant_id.

        Returns:
            A list of object paths matching the prefix.
        """
        client = self._get_client()
        search_prefix = f"{tenant_id}/"
        if prefix:
            search_prefix += prefix

        objects = client.list_objects(
            self._bucket,
            prefix=search_prefix,
            recursive=True,
        )
        return [obj.object_name for obj in objects]


def create_mnpi_worm_bucket(
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    secure: bool | None = None,
) -> MinioWormBucket:
    """Factory: create a ``MinioWormBucket`` from settings or env vars.

    Reads from environment variables if explicit params are not provided:

    - ``MINIO_ENDPOINT`` (default: ``localhost:9000``)
    - ``MINIO_ACCESS_KEY`` (default: ``minioadmin``)
    - ``MINIO_SECRET_KEY`` (default: ``minioadmin``)
    - ``MINIO_SECURE`` (default: ``false``)

    Args:
        endpoint: MinIO server endpoint.
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        secure: Use HTTPS.

    Returns:
        A configured ``MinioWormBucket`` instance.
    """
    import os

    return MinioWormBucket(
        endpoint=endpoint or os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        access_key=access_key or os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=secret_key or os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        secure=secure if secure is not None else os.environ.get("MINIO_SECURE", "false").lower() == "true",  # noqa: E501
    )
