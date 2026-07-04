"""Tests for MinIO WORM bucket manager for SEC 17a-4 MNPI audit retention.

Phase 15 Financial Services Compliance, D-004.

Uses ``unittest.mock`` to mock the MinIO client — no running MinIO
server required for unit tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from anonreq.models.audit import MnpiAuditEvent
from anonreq.storage.minio import (
    MNPI_WORM_BUCKET,
    MinioWormBucket,
    create_mnpi_worm_bucket,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_minio_client() -> MagicMock:
    """Return a mock MinIO client with common methods mocked."""
    client = MagicMock()
    client.bucket_exists.return_value = False
    return client


@pytest.fixture
def worm_bucket(mock_minio_client: MagicMock) -> MinioWormBucket:
    """Return a MinioWormBucket with a mocked MinIO client."""
    bucket = MinioWormBucket(
        endpoint="localhost:9000",
        access_key="testkey",
        secret_key="testsecret",
        secure=False,
    )
    # Replace internal client with mock
    bucket._client = mock_minio_client
    return bucket


@pytest.fixture
def sample_event() -> MnpiAuditEvent:
    """Return a sample MnpiAuditEvent for testing."""
    return MnpiAuditEvent(
        event_id="evt-001",
        tenant_id="acme-corp",
        session_id="sess-abc123",
        entity_type="MNPI_TICKER",
        policy_action="anonymize",
        detected_value_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        timestamp=datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
        policy_rule_id="policy-01",
    )


# ── Module Constants ─────────────────────────────────────────────────────────


class TestConstants:
    """Module-level constants."""

    def test_worm_bucket_name(self):
        """WORM bucket name is anonreq-mnpi-audit."""
        assert MNPI_WORM_BUCKET == "anonreq-mnpi-audit"


# ── Test 1: Bucket creation with WORM settings ───────────────────────────────


class TestBucketCreation:
    """Bucket existence check and creation."""

    @pytest.mark.asyncio
    async def test_ensure_bucket_creates_when_missing(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """ensure_bucket creates bucket with object_lock=True when missing."""
        mock_minio_client.bucket_exists.return_value = False

        result = await worm_bucket.ensure_bucket()

        assert result is True
        mock_minio_client.bucket_exists.assert_called_once_with(MNPI_WORM_BUCKET)
        mock_minio_client.make_bucket.assert_called_once_with(
            MNPI_WORM_BUCKET, object_lock=True
        )

    @pytest.mark.asyncio
    async def test_ensure_bucket_skips_when_exists(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """ensure_bucket skips creation when bucket already exists."""
        mock_minio_client.bucket_exists.return_value = True

        result = await worm_bucket.ensure_bucket()

        assert result is True
        mock_minio_client.make_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_bucket_returns_false_on_error(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """ensure_bucket returns False on S3 error."""
        from minio.error import S3Error

        mock_minio_client.bucket_exists.side_effect = S3Error(
            "ConnectionError", "Failed to connect", "localhost:9000", "", "", ""
        )

        result = await worm_bucket.ensure_bucket()

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_bucket_lazy_init(self):
        """MinioWormBucket lazily initializes the MinIO client."""
        bucket = MinioWormBucket(
            endpoint="localhost:9000",
            access_key="key",
            secret_key="secret",
            secure=False,
        )
        # Client should be None before first use
        assert bucket._client is None

        # After accessing through ensure_bucket, client should be set
        with patch("anonreq.storage.minio.Minio") as mock_minio_cls:
            mock_instance = MagicMock()
            mock_instance.bucket_exists.return_value = True
            mock_minio_cls.return_value = mock_instance

            result = await bucket.ensure_bucket()

            assert result is True
            mock_minio_cls.assert_called_once_with(
                "localhost:9000",
                access_key="key",
                secret_key="secret",
                secure=False,
            )


# ── Test 2: Store and retrieve audit events ──────────────────────────────────


class TestStoreAuditEvents:
    """Storing MNPI audit events."""

    @pytest.mark.asyncio
    async def test_store_audit_event_creates_object(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock, sample_event: MnpiAuditEvent
    ):
        """store_mnpi_audit_event uploads event JSON to the correct path."""
        object_path = await worm_bucket.store_mnpi_audit_event(sample_event)

        # Verify path format: tenant_id/year/month/day/event_id.json
        expected_path = "acme-corp/2026/07/04/evt-001.json"
        assert object_path == expected_path

        # Verify put_object was called
        mock_minio_client.put_object.assert_called_once()
        call_args = mock_minio_client.put_object.call_args
        assert call_args[0][0] == MNPI_WORM_BUCKET  # bucket
        assert call_args[0][1] == expected_path  # object_path
        assert call_args[1]["length"] > 0
        assert call_args[1]["content_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_store_sets_object_retention(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock, sample_event: MnpiAuditEvent
    ):
        """Stored events have COMPLIANCE retention set."""
        await worm_bucket.store_mnpi_audit_event(sample_event)

        # Verify set_object_retention was called
        mock_minio_client.set_object_retention.assert_called_once()
        call_args = mock_minio_client.set_object_retention.call_args

        # Retention is the third positional arg (bucket, path, retention)
        retention = call_args[0][2]
        assert retention.mode == "COMPLIANCE"
        assert retention.retain_until_date is not None

        # Verify retention is ~7 years in the future
        from datetime import timedelta

        expected_min = sample_event.timestamp + timedelta(days=2557 - 1)
        expected_max = sample_event.timestamp + timedelta(days=2557 + 1)
        assert expected_min <= retention.retain_until_date <= expected_max

    @pytest.mark.asyncio
    async def test_store_includes_policy_rule_id(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """Event with policy_rule_id stores the field."""
        event = MnpiAuditEvent(
            event_id="evt-002",
            tenant_id="bigbank",
            session_id="sess-xyz",
            entity_type="MNPI_DEAL",
            policy_action="block",
            detected_value_hash="deadbeef",
            timestamp=datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
            policy_rule_id="policy-42",
        )
        await worm_bucket.store_mnpi_audit_event(event)

        call_args = mock_minio_client.put_object.call_args
        body = call_args[1]["data"].read()
        payload = json.loads(body)
        assert payload["policy_rule_id"] == "policy-42"

    @pytest.mark.asyncio
    async def test_store_omits_policy_rule_id_when_none(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """Event without policy_rule_id omits the field from JSON."""
        event = MnpiAuditEvent(
            event_id="evt-003",
            tenant_id="bigbank",
            session_id="sess-xyz",
            entity_type="MNPI_TICKER",
            policy_action="flag",
            detected_value_hash="cafebabe",
            timestamp=datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
        )
        await worm_bucket.store_mnpi_audit_event(event)

        call_args = mock_minio_client.put_object.call_args
        body = call_args[1]["data"].read()
        payload = json.loads(body)
        assert "policy_rule_id" not in payload

    @pytest.mark.asyncio
    async def test_store_raises_on_s3_error(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock, sample_event: MnpiAuditEvent
    ):
        """S3 error during store propagates as S3Error."""
        from minio.error import S3Error

        mock_minio_client.put_object.side_effect = S3Error(
            "AccessDenied", "Access denied", MNPI_WORM_BUCKET, "", "", ""
        )

        with pytest.raises(S3Error):
            await worm_bucket.store_mnpi_audit_event(sample_event)


# ── Test 3: Retrieve audit events ────────────────────────────────────────────


class TestGetAuditEvents:
    """Retrieving MNPI audit events."""

    @pytest.mark.asyncio
    async def test_get_existing_event(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """get_audit_event returns parsed event for existing object."""
        event_data = {
            "event_id": "evt-001",
            "tenant_id": "acme-corp",
            "entity_type": "MNPI_TICKER",
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(event_data).encode()
        mock_minio_client.get_object.return_value = mock_response

        result = await worm_bucket.get_audit_event("acme-corp/2026/07/04/evt-001.json")

        assert result is not None
        assert result["event_id"] == "evt-001"
        assert result["tenant_id"] == "acme-corp"

    @pytest.mark.asyncio
    async def test_get_nonexistent_event_returns_none(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """get_audit_event returns None for missing object."""
        from minio.error import S3Error

        mock_minio_client.get_object.side_effect = S3Error(
            "NoSuchKey", "Object not found", MNPI_WORM_BUCKET, "", "", ""
        )

        result = await worm_bucket.get_audit_event("nonexistent/path.json")
        assert result is None


# ── Test 4: List audit events by tenant ───────────────────────────────────────


class TestListAuditEvents:
    """Listing MNPI audit events by tenant."""

    @pytest.mark.asyncio
    async def test_list_by_tenant(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """list_audit_events returns object paths for a tenant."""
        mock_obj_1 = MagicMock()
        mock_obj_1.object_name = "acme-corp/2026/07/04/evt-001.json"
        mock_obj_2 = MagicMock()
        mock_obj_2.object_name = "acme-corp/2026/07/04/evt-002.json"
        mock_minio_client.list_objects.return_value = [mock_obj_1, mock_obj_2]

        paths = await worm_bucket.list_audit_events("acme-corp")

        assert len(paths) == 2
        assert "acme-corp/2026/07/04/evt-001.json" in paths
        assert "acme-corp/2026/07/04/evt-002.json" in paths

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_events(
        self, worm_bucket: MinioWormBucket, mock_minio_client: MagicMock
    ):
        """list_audit_events returns empty list when no events."""
        mock_minio_client.list_objects.return_value = []

        paths = await worm_bucket.list_audit_events("empty-tenant")
        assert paths == []


# ── Test 5: MnpiAuditEvent model ─────────────────────────────────────────────


class TestMnpiAuditEventModel:
    """MnpiAuditEvent dataclass behavior."""

    def test_event_creation(self):
        """Creating an MnpiAuditEvent with all fields."""
        event = MnpiAuditEvent(
            event_id="test-001",
            tenant_id="acme",
            session_id="session-1",
            entity_type="MNPI_TICKER",
            policy_action="anonymize",
            detected_value_hash="abc123",
            policy_rule_id="rule-1",
        )
        assert event.event_id == "test-001"
        assert event.tenant_id == "acme"
        assert event.policy_action == "anonymize"
        assert event.timestamp is not None

    def test_event_default_timestamp(self):
        """Event timestamp defaults to now."""
        event = MnpiAuditEvent(
            event_id="test-002",
            tenant_id="acme",
            session_id="session-2",
            entity_type="MNPI_DEAL",
            policy_action="block",
            detected_value_hash="def456",
        )
        assert event.timestamp is not None
        assert event.policy_rule_id is None

    def test_event_no_raw_pii(self):
        """MnpiAuditEvent has no field for raw PII/MNPI values (T-15-01-01)."""
        event = MnpiAuditEvent(
            event_id="test-003",
            tenant_id="acme",
            session_id="session-3",
            entity_type="MNPI_TICKER",
            policy_action="flag",
            detected_value_hash="hash_only",
        )
        # Verify there's no field that could contain raw values
        assert not hasattr(event, "raw_value")
        assert not hasattr(event, "detected_value")
        # Only the hash is stored
        assert isinstance(event.detected_value_hash, str)

    def test_event_str_representation(self):
        """String representation does not leak value."""
        event = MnpiAuditEvent(
            event_id="test-004",
            tenant_id="acme",
            session_id="session-4",
            entity_type="MNPI_TICKER",
            policy_action="anonymize",
            detected_value_hash="secret_hash_value",
        )
        # __repr__ should not contain raw PII
        rep = repr(event)
        # It might or might not contain the hash depending on dataclass repr
        # but it should NOT have a field named 'raw_value'
        assert "raw_value" not in rep


# ── Test 6: Factory function ──────────────────────────────────────────────────


class TestFactory:
    """create_mnpi_worm_bucket factory."""

    def test_factory_uses_env_vars(self, monkeypatch):
        """Factory reads from env vars when no params given."""
        monkeypatch.setenv("MINIO_ENDPOINT", "minio.example.com:443")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "env_access")
        monkeypatch.setenv("MINIO_SECRET_KEY", "env_secret")
        monkeypatch.setenv("MINIO_SECURE", "true")

        bucket = create_mnpi_worm_bucket()

        assert bucket._endpoint == "minio.example.com:443"
        assert bucket._access_key == "env_access"
        assert bucket._secret_key == "env_secret"
        assert bucket._secure is True

    def test_factory_explicit_params_override_env(self, monkeypatch):
        """Explicit params to factory override environment variables."""
        monkeypatch.setenv("MINIO_ENDPOINT", "should-not-be-used:9000")

        bucket = create_mnpi_worm_bucket(
            endpoint="explicit-host:9000",
            access_key="explicit_key",
            secret_key="explicit_secret",
        )

        assert bucket._endpoint == "explicit-host:9000"
        assert bucket._access_key == "explicit_key"

    def test_factory_defaults(self):
        """Factory uses defaults when no params or env vars."""
        bucket = create_mnpi_worm_bucket()

        assert bucket._endpoint == "localhost:9000"
        assert bucket._access_key == "minioadmin"
        assert bucket._secret_key == "minioadmin"
        assert bucket._secure is False

    def test_factory_bucket_property(self, worm_bucket: MinioWormBucket):
        """bucket property returns the configured bucket name."""
        assert worm_bucket.bucket == MNPI_WORM_BUCKET
