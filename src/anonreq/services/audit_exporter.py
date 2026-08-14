"""Monthly compliance audit exporter.

Generates gzipped JSONL and Parquet exports for a target month,
uploads them to MinIO WORM, and tracks export metadata.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    raise ImportError(
        "pyarrow is required for Parquet export. "
        "Install with: pip install 'anonreq[exports]'"
    ) from None

import structlog
import yaml

try:
    from minio import Minio
    from minio.retention import Retention
except ImportError:
    raise ImportError(
        "minio is required for MinIO upload. "
        "Install with: pip install 'anonreq[storage]'"
    ) from None
from sqlalchemy import text

from anonreq.models.audit import AuditEvent, ExportResult
from anonreq.services.audit_chain import AuditChainService

logger = structlog.get_logger()


@dataclass
class MinioConfig:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    secure: bool = False
    worm_enabled: bool = True
    retention_days: int = 2557


@dataclass
class MonthlyConfig:
    enabled: bool
    schedule: str
    formats: list[str]
    compression: str


@dataclass
class ExportConfig:
    monthly: MonthlyConfig
    minio: MinioConfig


class AuditExporter:
    def __init__(self, audit_chain: AuditChainService, config: ExportConfig | None = None, config_path: str = "config/export.yaml") -> None:  # noqa: E501
        self._audit_chain = audit_chain
        self._minio_client: Minio | None = None

        if config is not None:
            self._config = config
        else:
            # Load from file or fallback to defaults
            try:
                with open(config_path) as f:
                    data = yaml.safe_load(f) or {}
                    cfg = data.get("export", {})

                    m_cfg = cfg.get("monthly", {})
                    monthly = MonthlyConfig(
                        enabled=m_cfg.get("enabled", True),
                        schedule=m_cfg.get("schedule", "0 0 5 * *"),
                        formats=m_cfg.get("formats", ["jsonl", "parquet"]),
                        compression=m_cfg.get("compression", "gzip"),
                    )

                    min_cfg = cfg.get("minio", {})
                    # Load access/secret keys from env variables if template values are present
                    access_key = min_cfg.get("access_key", "")
                    if "${" in access_key or not access_key:
                        access_key = os.environ.get("ANONREQ_MINIO_ACCESS_KEY", "minioadmin")
                    secret_key = min_cfg.get("secret_key", "")
                    if "${" in secret_key or not secret_key:
                        secret_key = os.environ.get("ANONREQ_MINIO_SECRET_KEY", "minioadmin")

                    minio = MinioConfig(
                        endpoint=min_cfg.get("endpoint", "http://minio:9000"),
                        bucket=min_cfg.get("bucket", "anonreq-audit-archives"),
                        access_key=access_key,
                        secret_key=secret_key,
                        secure=min_cfg.get("secure", False),
                        worm_enabled=min_cfg.get("worm_enabled", True),
                        retention_days=min_cfg.get("retention_days", 2557),
                    )

                    self._config = ExportConfig(monthly=monthly, minio=minio)
            except Exception:
                # Fallback defaults
                self._config = ExportConfig(
                    monthly=MonthlyConfig(True, "0 0 5 * *", ["jsonl", "parquet"], "gzip"),
                    minio=MinioConfig(
                        endpoint="localhost:9000",
                        bucket="anonreq-audit-archives",
                        access_key=os.environ.get("ANONREQ_MINIO_ACCESS_KEY", "minioadmin"),
                        secret_key=os.environ.get("ANONREQ_MINIO_SECRET_KEY", "minioadmin"),
                        secure=False,
                        worm_enabled=True,
                        retention_days=2557,
                    )
                )

    async def _get_minio_client(self) -> Minio:
        """Lazy-init MinIO client with WORM bucket config."""
        if self._minio_client is None:
            # Strip http/https prefix from endpoint for Minio SDK
            endpoint = self._config.minio.endpoint
            if endpoint.startswith("http://"):
                endpoint = endpoint[7:]
            elif endpoint.startswith("https://"):
                endpoint = endpoint[8:]

            self._minio_client = Minio(
                endpoint,
                access_key=self._config.minio.access_key,
                secret_key=self._config.minio.secret_key,
                secure=self._config.minio.secure,
            )

            # Ensure bucket exists
            bucket_name = self._config.minio.bucket
            try:
                if not self._minio_client.bucket_exists(bucket_name):
                    self._minio_client.make_bucket(bucket_name, object_lock=self._config.minio.worm_enabled)  # noqa: E501
            except Exception as e:
                logger.warning("minio.bucket_setup_failed", bucket=bucket_name, error=str(e))

        return self._minio_client

    async def export_month(self, year: int, month: int) -> ExportResult:
        """Export all audit events for the given month to MinIO and tracking."""
        # Calculate date boundaries
        date_from = datetime(year, month, 1, 0, 0, 0, tzinfo=UTC)
        if month == 12:
            date_to = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC) - timedelta(microseconds=1)
        else:
            date_to = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=UTC) - timedelta(microseconds=1)

        # 1. Fetch events from AuditChainService (no tenant_id filter -> get all events)
        events = await self._audit_chain.get_events(
            tenant_id=None,
            limit=10000000,
            date_from=date_from,
            date_to=date_to,
        )

        checksums = {}
        client = await self._get_minio_client()

        # Create temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            # 2. Generate JSONL if configured
            if "jsonl" in self._config.monthly.formats:
                local_jsonl_gz = os.path.join(tmpdir, f"audit-{year}-{month:02d}.jsonl.gz")
                checksum = await self._generate_jsonl(events, local_jsonl_gz)
                checksums["jsonl"] = checksum

                remote_jsonl = f"exports/audit-{year}-{month:02d}.jsonl.gz"
                await self._upload_to_minio(client, local_jsonl_gz, remote_jsonl)

            # 3. Generate Parquet if configured
            if "parquet" in self._config.monthly.formats:
                local_parquet = os.path.join(tmpdir, f"audit-{year}-{month:02d}.parquet")
                checksum = await self._generate_parquet(events, local_parquet)
                checksums["parquet"] = checksum

                remote_parquet = f"exports/audit-{year}-{month:02d}.parquet"
                await self._upload_to_minio(client, local_parquet, remote_parquet)

        # 4. Record export in PostgreSQL export_tracking table
        created_at = datetime.now(UTC)
        async with self._audit_chain._session_factory() as session:  # noqa: SIM117
            async with session.begin():
                await session.execute(
                    text(
                        "INSERT INTO export_tracking (year, month, event_count, formats, checksums_json, created_at) "  # noqa: E501
                        "VALUES (:year, :month, :event_count, :formats, :checksums_json, :created_at)"  # noqa: E501
                    ),
                    {
                        "year": year,
                        "month": month,
                        "event_count": len(events),
                        "formats": json.dumps(self._config.monthly.formats),
                        "checksums_json": json.dumps(checksums),
                        "created_at": created_at,
                    }
                )

        # 5. Emit compliance_export_completed audit event
        audit_evt = AuditEvent(
            event_id=str(uuid.uuid4()),
            prev_hash=None,
            hash="",
            timestamp=created_at,
            tenant_id="default",
            request_id=None,
            policy_id=None,
            decision=None,
            provider=None,
            latency_ms=None,
            event_type="compliance_export_completed",
            operator_id=None,
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json=json.dumps({
                "year": year,
                "month": month,
                "event_count": len(events),
                "checksums": checksums,
            }),
            retention_days=2557,
        )
        try:
            await self._audit_chain.store_event(audit_evt)
        except Exception as e:
            logger.error("audit_exporter.log_audit_failed", error=str(e))

        return ExportResult(
            year=year,
            month=month,
            formats=self._config.monthly.formats,
            event_count=len(events),
            checksums=checksums,
            created_at=created_at,
        )

    async def _generate_jsonl(self, events: list[AuditEvent], path: str) -> str:
        """Write events as gzipped JSONL. Returns SHA-384 checksum."""
        sha384 = hashlib.sha384()
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for e in events:
                evt_dict = {
                    "event_id": e.event_id,
                    "prev_hash": e.prev_hash,
                    "hash": e.hash,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "tenant_id": e.tenant_id,
                    "request_id": e.request_id,
                    "policy_id": e.policy_id,
                    "decision": e.decision,
                    "provider": e.provider,
                    "latency_ms": e.latency_ms,
                    "event_type": e.event_type,
                    "operator_id": e.operator_id,
                    "change_type": e.change_type,
                    "prev_value_hash": e.prev_value_hash,
                    "new_value_hash": e.new_value_hash,
                    "metadata_json": e.metadata_json,
                }
                line = json.dumps(evt_dict) + "\n"
                f.write(line)

        # Calculate checksum
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha384.update(chunk)
        return sha384.hexdigest()

    async def _generate_parquet(self, events: list[AuditEvent], path: str) -> str:
        """Write events as Parquet. Returns SHA-384 checksum."""
        data = {
            "event_id": [e.event_id for e in events],
            "prev_hash": [e.prev_hash for e in events],
            "hash": [e.hash for e in events],
            "timestamp": [e.timestamp.isoformat() if e.timestamp else None for e in events],
            "tenant_id": [e.tenant_id for e in events],
            "request_id": [e.request_id for e in events],
            "policy_id": [e.policy_id for e in events],
            "decision": [e.decision for e in events],
            "provider": [e.provider for e in events],
            "latency_ms": [e.latency_ms for e in events],
            "event_type": [e.event_type for e in events],
            "operator_id": [e.operator_id for e in events],
            "change_type": [e.change_type for e in events],
            "prev_value_hash": [e.prev_value_hash for e in events],
            "new_value_hash": [e.new_value_hash for e in events],
            "metadata_json": [e.metadata_json for e in events],
        }

        schema = pa.schema([
            ("event_id", pa.string()),
            ("prev_hash", pa.string()),
            ("hash", pa.string()),
            ("timestamp", pa.string()),
            ("tenant_id", pa.string()),
            ("request_id", pa.string()),
            ("policy_id", pa.string()),
            ("decision", pa.string()),
            ("provider", pa.string()),
            ("latency_ms", pa.int64()),
            ("event_type", pa.string()),
            ("operator_id", pa.string()),
            ("change_type", pa.string()),
            ("prev_value_hash", pa.string()),
            ("new_value_hash", pa.string()),
            ("metadata_json", pa.string()),
        ])

        table = pa.Table.from_pydict(data, schema=schema)
        pq.write_table(table, path)  # type: ignore[no-untyped-call]

        # Calculate checksum
        sha384 = hashlib.sha384()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha384.update(chunk)
        return sha384.hexdigest()

    async def _upload_to_minio(self, client: Minio, local_path: str, remote_path: str) -> None:
        """Upload file to MinIO WORM bucket with retention headers."""
        bucket_name = self._config.minio.bucket

        # Perform upload
        client.fput_object(bucket_name, remote_path, local_path)

        # Set Object Lock Retention if enabled
        if self._config.minio.worm_enabled:
            retain_until = datetime.now(UTC) + timedelta(days=self._config.minio.retention_days)
            try:
                client.set_object_retention(
                    bucket_name,
                    remote_path,
                    Retention("COMPLIANCE", retain_until)
                )
            except Exception as exc:
                logger.warning("minio.retention_setup_failed", path=remote_path, error=str(exc))

    async def run_scheduled_export(self) -> ExportResult | None:
        """Called by scheduler. Exports previous month if not already exported."""
        now = datetime.now(UTC)
        # Compute previous month
        first_of_this_month = now.replace(day=1)
        prev_month_dt = first_of_this_month - timedelta(days=1)
        year, month = prev_month_dt.year, prev_month_dt.month

        # Check if already exported
        async with self._audit_chain._session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM export_tracking WHERE year = :year AND month = :month"),
                {"year": year, "month": month}
            )
            count = result.scalar() or 0
            if count > 0:
                return None

        return await self.export_month(year, month)

    async def get_export_history(self, limit: int = 12) -> list[ExportResult]:
        """Return recent export results."""
        async with self._audit_chain._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT year, month, event_count, formats, checksums_json, created_at "
                    "FROM export_tracking ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit}
            )
            rows = result.mappings().all()

            history = []
            for r in rows:
                formats = json.loads(r["formats"])
                checksums = json.loads(r["checksums_json"])

                ts = r["created_at"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)

                history.append(ExportResult(
                    year=r["year"],
                    month=r["month"],
                    formats=formats,
                    event_count=r["event_count"],
                    checksums=checksums,
                    created_at=ts,
                ))
            return history
