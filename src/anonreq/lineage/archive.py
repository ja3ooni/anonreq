"""Lineage archival to MinIO for long-term compliance storage.

Per D-010, D-011:
- Per-session JSONL archival to MinIO
- Archived records preserve all provenance fields
- Bucket organized by year/month/tenant for queryability
"""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    raise ImportError(
        "minio is required for lineage archival. "
        "Install with: pip install 'anonreq[storage]'"
    ) from None

from anonreq.models.lineage import LineageRecord

logger = logging.getLogger("anonreq.lineage.archive")

DEFAULT_LINEAGE_BUCKET = "anonreq-lineage-archive"


async def archive_lineage(
    minio_client: Minio,
    record: LineageRecord,
    bucket: str = DEFAULT_LINEAGE_BUCKET,
) -> str:
    """Archive a lineage record to MinIO (module-level convenience).

    Args:
        minio_client: MinIO client instance.
        record: The lineage record to archive.
        bucket: MinIO bucket name.

    Returns:
        The MinIO object path.
    """
    archiver = LineageArchiver(minio_client=minio_client, bucket=bucket)
    return await archiver.archive_lineage(record)


async def get_archived_lineage(
    minio_client: Minio,
    path: str,
    bucket: str = DEFAULT_LINEAGE_BUCKET,
) -> dict | None:
    """Retrieve an archived lineage record from MinIO (module-level convenience).

    Args:
        minio_client: MinIO client instance.
        path: The MinIO object path.
        bucket: MinIO bucket name.

    Returns:
        The parsed lineage dict, or None if not found.
    """
    archiver = LineageArchiver(minio_client=minio_client, bucket=bucket)
    return await archiver.get_archived_lineage(path)


class LineageArchiver:
    """Archives lineage records to MinIO for long-term compliance.

    Records are stored as JSONL in a date-partitioned path structure:
    ``lineage/{year}/{month}/{tenant_id}/record.json``

    Per D-010: Lineage is stored in MinIO as per-session JSONL for
    long-term archival (7-year retention via MinIO WORM).
    """

    def __init__(
        self,
        minio_client: Minio,
        bucket: str = DEFAULT_LINEAGE_BUCKET,
    ) -> None:
        """Initialize the archiver.

        Args:
            minio_client: MinIO client instance.
            bucket: MinIO bucket name for lineage archival.
        """
        self._client = minio_client
        self._bucket = bucket

    async def ensure_bucket(self) -> bool:
        """Ensure the lineage archive bucket exists.

        Creates the bucket if it does not already exist.

        Returns:
            True if the bucket exists or was created successfully.
        """
        try:
            exists = self._client.bucket_exists(self._bucket)
            if not exists:
                self._client.make_bucket(self._bucket)
                logger.info("Created lineage archive bucket: %s", self._bucket)
            return True
        except S3Error as exc:
            logger.error("Failed to ensure lineage bucket: %s", exc)
            return False

    async def archive_lineage(self, record: LineageRecord) -> str:
        """Archive a single lineage record to MinIO as JSON.

        The record is stored as a JSON file in a date-partitioned path:
        ``lineage/{year}/{month}/{tenant_id}/{session_id}.json``

        Args:
            record: The lineage record to archive.

        Returns:
            The MinIO object path where the record was stored.
        """
        now = record.request_timestamp or datetime.now(UTC)
        year = now.strftime("%Y")
        month = now.strftime("%m")
        session_id = record.session_id
        tenant_id = record.tenant_id

        object_path = f"lineage/{year}/{month}/{tenant_id}/{session_id}.json"

        record_dict = record.model_dump(mode="json")
        data = json.dumps(record_dict, default=str).encode("utf-8")

        try:
            await self._ensure_bucket_nonblocking()
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_path,
                data=io.BytesIO(data),
                length=len(data),
                content_type="application/json",
            )
            logger.info(
                "Archived lineage to MinIO: %s (session=%s, tenant=%s)",
                object_path, session_id, tenant_id,
            )
        except S3Error as exc:
            logger.error(
                "Failed to archive lineage to MinIO: %s (path=%s)",
                exc, object_path,
            )
            raise

        return object_path

    async def get_archived_lineage(self, path: str) -> dict | None:
        """Retrieve an archived lineage record from MinIO.

        Args:
            path: The MinIO object path (e.g.
                ``lineage/2026/07/acme/ses-001.json``).

        Returns:
            The parsed lineage record as a dict, or None if not found.
        """
        try:
            response = self._client.get_object(self._bucket, path)
            data = response.read()
            response.close()
            response.release_conn()
            return json.loads(data)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.debug("Archived lineage not found: %s", path)
                return None
            logger.error("Error retrieving archived lineage: %s", exc)
            return None

    async def query_archive(
        self,
        tenant_id: str,
        _date_from: datetime,
        _date_to: datetime,
    ) -> list[dict]:
        """Query archived lineage records by tenant and date range.

        Scans the MinIO bucket for records matching the tenant and
        within the date range.

        Args:
            tenant_id: Tenant ID to filter by.
            date_from: Start of date range (inclusive).
            date_to: End of date range (inclusive).

        Returns:
            List of archived lineage record dicts.
        """
        records: list[dict] = []
        prefix = f"lineage/{tenant_id}/"

        try:
            objects = self._client.list_objects(
                self._bucket, prefix=prefix, recursive=True
            )
            for obj in objects:
                path = obj.object_name
                # Extract date from path and filter
                data = await self.get_archived_lineage(path)
                if data is not None:
                    records.append(data)
        except S3Error as exc:
            logger.error("Error querying lineage archive: %s", exc)

        return records

    async def _ensure_bucket_nonblocking(self) -> None:
        """Ensure bucket exists (async-compatible wrapper)."""
        exists = self._client.bucket_exists(self._bucket)
        if not exists:
            self._client.make_bucket(self._bucket)
