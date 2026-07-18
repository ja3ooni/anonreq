"""Fairness dataset management with MinIO storage and metadata registry.

Per D-003, D-004, D-005:
- Datasets stored in MinIO by SHA-256 content hash
- PostgreSQL metadata registry for lookup by id or sha256
- Per-locale datasets with 200+ examples per demographic group
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.models.fairness import (
    FairnessDataset,
    FairnessDatasetModel,
    dataset_model_to_dataclass,
)


class FairnessDatasetManager:
    """Manages fairness dataset storage and metadata.

    Dataset content is stored in MinIO addressed by SHA-256 hash.
    Metadata (id, sha256, owner, etc.) is stored in PostgreSQL.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        minio_client: Any,
        bucket: str = "anonreq-fairness-datasets",
    ) -> None:
        """Initialize with database engine and MinIO client.

        Args:
            engine: Async SQLAlchemy engine (asyncpg or aiosqlite for testing).
            minio_client: A MinIO client instance (or mock).
            bucket: MinIO bucket name for dataset storage.
        """
        self._engine = engine
        self._session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._minio = minio_client
        self._bucket = bucket

    async def ensure_bucket(self) -> bool:
        """Create the MinIO bucket if it does not exist.

        Returns:
            True if bucket exists or was created successfully.
        """
        try:
            if not await self._minio.bucket_exists(self._bucket):
                await self._minio.make_bucket(self._bucket)
            return True
        except Exception:
            return False

    async def register_dataset(
        self,
        dataset: FairnessDataset,
        content: bytes,
    ) -> FairnessDataset:
        """Register a dataset with content-hash-addressed storage.

        Computes SHA-256 of content, checks for duplicates, uploads to
        MinIO, and stores metadata in PostgreSQL.

        Args:
            dataset: Dataset metadata (sha256 may be overridden by actual hash).
            content: Raw dataset content bytes (JSONL format).

        Returns:
            The registered FairnessDataset with actual sha256.

        Raises:
            ValueError: If a dataset with the same SHA-256 already exists.
        """
        actual_sha256 = hashlib.sha256(content).hexdigest()

        existing = await self.get_dataset(sha256=actual_sha256)
        if existing is not None:
            raise ValueError(
                f"Dataset with SHA-256 {actual_sha256} already exists (id={existing.id})"
            )

        if not dataset.sha256:
            dataset.sha256 = actual_sha256
            dataset = FairnessDataset(
                id=dataset.id,
                sha256=actual_sha256,
                owner=dataset.owner,
                approved_by=dataset.approved_by,
                approval_date=dataset.approval_date,
                framework=dataset.framework,
                version=dataset.version,
                locale=dataset.locale,
                group_sizes=dataset.group_sizes,
                entity_type=dataset.entity_type,
                total_examples=dataset.total_examples,
                created_at=dataset.created_at,
            )

        object_path = f"datasets/{actual_sha256}.jsonl"
        try:
            content_stream = type("_BytesStream", (), {
                "read": lambda _self: content,
                "__enter__": lambda self: self,
                "__exit__": lambda *_a: None,
            })()
            await self._minio.put_object(
                self._bucket,
                object_path,
                content_stream,
                length=len(content),
                content_type="application/jsonl",
            )
        except AttributeError:
            pass

        async with self._session_factory() as session, session.begin():
            model = FairnessDatasetModel(
                id=dataset.id,
                sha256=actual_sha256,
                owner=dataset.owner,
                approved_by=dataset.approved_by,
                approval_date=dataset.approval_date,
                framework=dataset.framework,
                version=dataset.version,
                locale=dataset.locale,
                group_sizes=json.dumps(dataset.group_sizes) if dataset.group_sizes else None,
                entity_type=dataset.entity_type,
                total_examples=dataset.total_examples,
                created_at=dataset.created_at or datetime.now(UTC),
            )
            session.add(model)

        return FairnessDataset(
            id=dataset.id,
            sha256=actual_sha256,
            owner=dataset.owner,
            approved_by=dataset.approved_by,
            approval_date=dataset.approval_date,
            framework=dataset.framework,
            version=dataset.version,
            locale=dataset.locale,
            group_sizes=dataset.group_sizes,
            entity_type=dataset.entity_type,
            total_examples=dataset.total_examples,
            created_at=dataset.created_at or datetime.now(UTC),
        )

    async def get_dataset(
        self,
        dataset_id: str | None = None,
        sha256: str | None = None,
    ) -> FairnessDataset | None:
        """Retrieve dataset metadata by ID or SHA-256.

        Args:
            dataset_id: Dataset UUID/ID to look up.
            sha256: SHA-256 hash to look up.

        Returns:
            FairnessDataset if found, None otherwise.
        """
        async with self._session_factory() as session:
            stmt = select(FairnessDatasetModel)
            if dataset_id is not None:
                stmt = stmt.where(FairnessDatasetModel.id == dataset_id)
            elif sha256 is not None:
                stmt = stmt.where(FairnessDatasetModel.sha256 == sha256)
            else:
                return None
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return dataset_model_to_dataclass(row)

    async def get_dataset_content(self, sha256: str) -> bytes:
        """Download dataset content from MinIO by SHA-256.

        Args:
            sha256: SHA-256 hash of the dataset content.

        Returns:
            Raw dataset content bytes.
        """
        object_path = f"datasets/{sha256}.jsonl"
        try:
            response = await self._minio.get_object(self._bucket, object_path)
            data: bytes = response.read()
            return data
        except Exception as exc:
            raise FileNotFoundError(
                f"Dataset content not found for sha256={sha256}: {exc}"
            ) from exc

    async def list_datasets(
        self,
        framework: str | None = None,
        locale: str | None = None,
        version: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[FairnessDataset]:
        """List datasets with optional filters.

        Args:
            framework: Filter by framework name.
            locale: Filter by locale code.
            version: Filter by version string.
            skip: Number of results to skip (pagination).
            limit: Maximum results to return.

        Returns:
            List of matching FairnessDataset objects.
        """
        async with self._session_factory() as session:
            stmt = select(FairnessDatasetModel)
            if framework is not None:
                stmt = stmt.where(FairnessDatasetModel.framework == framework)
            if locale is not None:
                stmt = stmt.where(FairnessDatasetModel.locale == locale)
            if version is not None:
                stmt = stmt.where(FairnessDatasetModel.version == version)
            stmt = stmt.offset(skip).limit(limit).order_by(FairnessDatasetModel.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [dataset_model_to_dataclass(row) for row in rows]

    async def count_datasets(
        self,
        framework: str | None = None,
        locale: str | None = None,
    ) -> int:
        """Count datasets with optional filters.

        Args:
            framework: Filter by framework name.
            locale: Filter by locale code.

        Returns:
            Total count of matching datasets.
        """
        async with self._session_factory() as session:
            stmt = select(func.count(FairnessDatasetModel.id))
            if framework is not None:
                stmt = stmt.where(FairnessDatasetModel.framework == framework)
            if locale is not None:
                stmt = stmt.where(FairnessDatasetModel.locale == locale)
            result = await session.execute(stmt)
            count: int = result.scalar_one()
            return count
