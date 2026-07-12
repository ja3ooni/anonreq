"""Tests for fairness dataset models and management.

Uses SQLite in-memory for DB and a mock MinIO client.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.fairness.datasets import FairnessDatasetManager
from anonreq.models.fairness import (
    Base,
    DemographicResult,
    FairnessDataset,
    FairnessEvaluation,
    FairnessResult,
)


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with the fairness schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def mock_minio():
    """Create a mock MinIO client that stores objects in a dict."""

    class MockMinio:
        def __init__(self):
            self._buckets: set[str] = set()
            self._objects: dict[str, bytes] = {}

        async def bucket_exists(self, bucket: str) -> bool:
            return bucket in self._buckets

        async def make_bucket(self, bucket: str) -> None:
            self._buckets.add(bucket)

        async def put_object(self, bucket, object_path, data, length=None, content_type=None, *args, **kwargs):
            self._objects[object_path] = data.read() if hasattr(data, 'read') else data

        async def get_object(self, _bucket, object_path):
            class Response:
                def __init__(self, data):
                    self._data = data

                def read(self):
                    return self._data

            data = self._objects.get(object_path)
            if data is None:
                raise FileNotFoundError(f"Object {object_path} not found")
            return Response(data)

    return MockMinio()


@pytest.fixture
async def manager(engine, mock_minio):
    """Create a FairnessDatasetManager with test engine and mock MinIO."""
    return FairnessDatasetManager(engine, mock_minio)


class TestFairnessDatasetModel:
    """Tests for FairnessDataset dataclass."""

    def test_dataset_creates_with_required_fields(self):
        """Test 1: FairnessDataset includes id, sha256, owner, approved_by, approval_date, framework, version."""  # noqa: E501
        ds = FairnessDataset(
            id="ds_001",
            sha256="abc123def456",
            owner="alice",
            approved_by="compliance-team",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="en-US",
        )
        assert ds.id == "ds_001"
        assert ds.sha256 == "abc123def456"
        assert ds.owner == "alice"
        assert ds.approved_by == "compliance-team"
        assert ds.approval_date == datetime(2026, 6, 20, tzinfo=UTC)
        assert ds.framework == "bias-v1"
        assert ds.version == "1.0"
        assert ds.locale == "en-US"

    def test_dataset_defaults(self):
        """Test dataset uses sensible defaults for optional fields."""
        ds = FairnessDataset(
            id="ds_002",
            sha256="def789",
            owner="bob",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="de-DE",
        )
        assert ds.entity_type == "PERSON"
        assert ds.total_examples == 0
        assert ds.group_sizes == {}

    def test_dataset_with_group_sizes(self):
        """Dataset stores per-group example counts."""
        ds = FairnessDataset(
            id="ds_003",
            sha256="ghi012",
            owner="carol",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="2.0",
            locale="fr-FR",
            group_sizes={"male": 250, "female": 250, "non_binary": 200},
            entity_type="EMAIL",
            total_examples=700,
        )
        assert ds.group_sizes["male"] == 250
        assert ds.group_sizes["female"] == 250
        assert ds.group_sizes["non_binary"] == 200
        assert ds.total_examples == 700
        assert ds.entity_type == "EMAIL"


class TestDemographicResult:
    """Tests for DemographicResult computation."""

    def test_recall_computed_automatically(self):
        """Recall is computed as detected/total in __post_init__."""
        dr = DemographicResult(group="female", total=100, detected=95)
        assert dr.recall == 0.95

    def test_recall_zero_when_no_examples(self):
        """Recall is 0.0 when total is 0."""
        dr = DemographicResult(group="male", total=0, detected=0)
        assert dr.recall == 0.0

    def test_recall_perfect_detection(self):
        """Recall is 1.0 when all detected."""
        dr = DemographicResult(group="male", total=50, detected=50)
        assert dr.recall == 1.0


class TestFairnessResult:
    """Tests for FairnessResult threshold evaluation."""

    def test_passed_when_disparity_within_threshold(self):
        """Test 3: Disparity ≤ 0.05 → result.passed = True."""
        result = FairnessResult(
            entity_type="PERSON",
            overall_recall=0.95,
            demographic_results=[
                DemographicResult(group="male", total=100, detected=96),
                DemographicResult(group="female", total=100, detected=94),
            ],
            max_disparity=0.02,
            threshold=0.05,
        )
        assert result.passed is True
        assert result.max_disparity <= result.threshold

    def test_failed_when_disparity_exceeds_threshold(self):
        """Test 4: Disparity > 0.05 → result.passed = False."""
        result = FairnessResult(
            entity_type="PERSON",
            overall_recall=0.85,
            demographic_results=[
                DemographicResult(group="male", total=100, detected=95),
                DemographicResult(group="female", total=100, detected=75),
            ],
            max_disparity=0.20,
            threshold=0.05,
        )
        assert result.passed is False
        assert result.max_disparity > result.threshold

    def test_passed_with_exact_threshold(self):
        """Result passes when disparity equals threshold."""
        result = FairnessResult(
            entity_type="EMAIL",
            overall_recall=0.90,
            demographic_results=[
                DemographicResult(group="male", total=100, detected=95),
                DemographicResult(group="female", total=100, detected=90),
            ],
            max_disparity=0.05,
            threshold=0.05,
        )
        assert result.passed is True


class TestFairnessEvaluation:
    """Tests for FairnessEvaluation aggregate logic."""

    def test_overall_passed_all_pass(self):
        """All results pass → overall_passed = True."""
        eval_obj = FairnessEvaluation(
            id="eval_001",
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.95,
                    demographic_results=[DemographicResult(group="male", total=100, detected=95)],
                    max_disparity=0.0,
                    threshold=0.05,
                ),
                FairnessResult(
                    entity_type="EMAIL",
                    overall_recall=0.97,
                    demographic_results=[DemographicResult(group="female", total=100, detected=97)],
                    max_disparity=0.0,
                    threshold=0.05,
                ),
            ],
        )
        assert eval_obj.overall_passed is True

    def test_overall_failed_one_fails(self):
        """One result fails → overall_passed = False."""
        eval_obj = FairnessEvaluation(
            id="eval_002",
            results=[
                FairnessResult(
                    entity_type="PERSON",
                    overall_recall=0.95,
                    demographic_results=[DemographicResult(group="male", total=100, detected=95)],
                    max_disparity=0.0,
                    threshold=0.05,
                ),
                FairnessResult(
                    entity_type="PHONE",
                    overall_recall=0.70,
                    demographic_results=[
                        DemographicResult(group="male", total=100, detected=85),
                        DemographicResult(group="female", total=100, detected=55),
                    ],
                    max_disparity=0.30,
                    threshold=0.05,
                ),
            ],
        )
        assert eval_obj.overall_passed is False

    def test_supports_git_sha(self):
        """Evaluation supports optional git_sha for build traceability."""
        eval_obj = FairnessEvaluation(
            id="eval_003",
            git_sha="a1b2c3d4e5f6",
            dataset_id="ds_001",
        )
        assert eval_obj.git_sha == "a1b2c3d4e5f6"
        assert eval_obj.dataset_id == "ds_001"


class TestFairnessDatasetManager:
    """Tests for dataset management operations."""

    async def test_register_dataset_stores_metadata(self, manager):
        """Test 2: register_dataset stores dataset metadata in PostgreSQL."""
        ds = FairnessDataset(
            id="ds_reg_001",
            sha256="",
            owner="alice",
            approved_by="compliance-team",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="en-US",
            entity_type="PERSON",
            total_examples=500,
        )
        content = json.dumps({"text": "test"}).encode("utf-8")
        registered = await manager.register_dataset(ds, content)

        assert registered.id == "ds_reg_001"
        assert len(registered.sha256) == 64
        assert registered.sha256 != ""

    async def test_get_dataset_by_id(self, manager):
        """Test 3: get_dataset retrieves dataset by id."""
        ds = FairnessDataset(
            id="ds_get_001",
            sha256="",
            owner="bob",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="de-DE",
            entity_type="EMAIL",
            total_examples=300,
        )
        content = b'{"text": "Test content"}'
        registered = await manager.register_dataset(ds, content)

        retrieved = await manager.get_dataset(dataset_id=registered.id)
        assert retrieved is not None
        assert retrieved.id == "ds_get_001"
        assert retrieved.locale == "de-DE"
        assert retrieved.entity_type == "EMAIL"

    async def test_get_dataset_by_sha256(self, manager):
        """get_dataset retrieves dataset by sha256."""
        ds = FairnessDataset(
            id="ds_sha_001",
            sha256="",
            owner="carol",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="fr-FR",
        )
        content = b'{"text": "Bonjour"}'
        registered = await manager.register_dataset(ds, content)

        retrieved = await manager.get_dataset(sha256=registered.sha256)
        assert retrieved is not None
        assert retrieved.id == "ds_sha_001"
        assert retrieved.sha256 == registered.sha256

    async def test_get_dataset_returns_none_for_missing(self, manager):
        """get_dataset returns None for non-existent dataset."""
        retrieved = await manager.get_dataset(dataset_id="nonexistent")
        assert retrieved is None

        retrieved = await manager.get_dataset(sha256="0000000000000000000000000000000000000000000000000000000000000000")  # noqa: E501
        assert retrieved is None

    async def test_duplicate_detection_by_hash(self, manager):
        """Test 5: Duplicate content raises ValueError."""
        ds1 = FairnessDataset(
            id="ds_dup_001",
            sha256="",
            owner="alice",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="en-US",
        )
        content = b'{"text": "Duplicate content"}'
        await manager.register_dataset(ds1, content)

        ds2 = FairnessDataset(
            id="ds_dup_002",
            sha256="",
            owner="bob",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="en-US",
        )
        with pytest.raises(ValueError, match="already exists"):
            await manager.register_dataset(ds2, content)

    async def test_list_datasets_filters_by_locale(self, manager):
        """Test 4: list_datasets filters by locale."""
        content_base = b'{"text": "test"}'
        for i, (locale, fw) in enumerate([("en-US", "v1"), ("de-DE", "v1"), ("en-US", "v2")]):
            ds = FairnessDataset(
                id=f"ds_list_{i}",
                sha256="",
                owner="tester",
                approved_by="compliance",
                approval_date=datetime(2026, 6, 20, tzinfo=UTC),
                framework=fw,
                version="1.0",
                locale=locale,
            )
            content = content_base + str(i).encode()
            await manager.register_dataset(ds, content)

        en_results = await manager.list_datasets(locale="en-US")
        assert len(en_results) == 2

        de_results = await manager.list_datasets(locale="de-DE")
        assert len(de_results) == 1

    async def test_list_datasets_filters_by_framework(self, manager):
        """list_datasets filters by framework."""
        content_base = b'{"text": "fw"}'
        for i, fw in enumerate([("v1", "1.0"), ("v2", "1.0"), ("v1", "2.0")]):
            ds = FairnessDataset(
                id=f"ds_fw_{i}",
                sha256="",
                owner="tester",
                approved_by="compliance",
                approval_date=datetime(2026, 6, 20, tzinfo=UTC),
                framework=fw[0],
                version=fw[1],
                locale="en-US",
            )
            content = content_base + str(i).encode()
            await manager.register_dataset(ds, content)

        v1_results = await manager.list_datasets(framework="v1")
        assert len(v1_results) == 2

        v2_results = await manager.list_datasets(framework="v2")
        assert len(v2_results) == 1

    async def test_list_datasets_pagination(self, manager):
        """list_datasets respects skip and limit."""
        for i in range(5):
            ds = FairnessDataset(
                id=f"ds_pg_{i}",
                sha256="",
                owner="tester",
                approved_by="compliance",
                approval_date=datetime(2026, 6, 20, tzinfo=UTC),
                framework="v1",
                version="1.0",
                locale="en-US",
            )
            content = f'{{"text": "page_{i}"}}'.encode()
            await manager.register_dataset(ds, content)

        all_results = await manager.list_datasets(limit=10)
        assert len(all_results) == 5

        limited = await manager.list_datasets(limit=2)
        assert len(limited) == 2

    async def test_ensure_bucket(self, mock_minio, engine):
        """Bucket creation works."""
        manager = FairnessDatasetManager(engine, mock_minio)
        result = await manager.ensure_bucket()
        assert result is True

    async def test_dataset_content_stored_by_hash(self, manager):
        """Test 5: Dataset content stored in MinIO by content hash."""
        ds = FairnessDataset(
            id="ds_store_001",
            sha256="",
            owner="alice",
            approved_by="compliance",
            approval_date=datetime(2026, 6, 20, tzinfo=UTC),
            framework="bias-v1",
            version="1.0",
            locale="en-US",
        )
        content = b'{"text": "Store me by hash"}'
        registered = await manager.register_dataset(ds, content)

        retrieved = await manager.get_dataset(sha256=registered.sha256)
        assert retrieved is not None
        assert retrieved.sha256 == registered.sha256

    async def test_per_locale_datasets(self, manager):
        """Test 6: Multiple locales supported."""
        locales = ["en-US", "de-DE", "fr-FR"]
        for i, locale in enumerate(locales):
            ds = FairnessDataset(
                id=f"ds_locale_{i}",
                sha256="",
                owner="tester",
                approved_by="compliance",
                approval_date=datetime(2026, 6, 20, tzinfo=UTC),
                framework="bias-v1",
                version="1.0",
                locale=locale,
            )
            content = f'{{"text": "Hello in {locale}"}}'.encode()
            await manager.register_dataset(ds, content)

        for locale in locales:
            datasets = await manager.list_datasets(locale=locale)
            assert len(datasets) == 1
            assert datasets[0].locale == locale
