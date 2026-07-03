"""Tests for the CA certificate manager with dual-path management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from anonreq.proxy.ca_manager import (
    CAManager,
    CAManagerError,
    _generate_self_signed_ca,
)


class TestCAManager:
    """Tests for CAManager initialization and basic operations."""

    @pytest.fixture
    def ca_dir(self):
        """Provide a temporary CA directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    async def manager(self, ca_dir):
        """Create a CAManager with a test CA directory."""
        m = CAManager(ca_dir=ca_dir, debounce=0.5)
        yield m
        await m.close()

    @pytest.fixture
    def sample_ca(self):
        """Generate a test CA cert+key pair."""
        cert, key, cert_pem, key_pem = _generate_self_signed_ca(cn="Test CA")
        return cert, key, cert_pem.decode("utf-8"), key_pem.decode("utf-8")

    async def test_get_ca_info_returns_none_before_upload(self, manager):
        """Test 1: get_ca_info() returns None before any CA is loaded."""
        info = await manager.get_ca_info()
        assert info is None

    async def test_upload_ca_cert_stores_and_returns_metadata(self, manager, sample_ca):
        """Test 2: upload_ca_cert stores cert and returns correct metadata."""
        _, _, cert_pem, key_pem = sample_ca
        result = await manager.upload_ca_cert(cert_pem, key_pem, label="test-cert")

        assert "serial" in result
        assert "subject" in result
        assert result["subject"] == "CN=Test CA"
        assert "not_after" in result

    async def test_upload_writes_files_to_ca_dir(self, manager, ca_dir, sample_ca):
        """Test 3: upload_ca_cert writes PEM files to the CA directory."""
        cert, key, cert_pem, key_pem = sample_ca
        result = await manager.upload_ca_cert(cert_pem, key_pem)

        serial = result["serial"]
        cert_file = Path(ca_dir) / f"{serial}.pem"
        key_file = Path(ca_dir) / f"{serial}.key"

        assert cert_file.exists()
        assert key_file.exists()
        assert cert_file.stat().st_mode & 0o777 == 0o600
        assert key_file.stat().st_mode & 0o777 == 0o600

    async def test_get_ca_info_returns_active_cert(self, manager, sample_ca):
        """Test 4: get_ca_info returns the active CA cert metadata."""
        cert, _, cert_pem, key_pem = sample_ca
        await manager.upload_ca_cert(cert_pem, key_pem)
        info = await manager.get_ca_info()

        assert info is not None
        assert info["serial"] == cert.serial_number
        assert info["subject"] == "CN=Test CA"
        assert "not_after" in info
        assert "not_before" in info
        assert "uploaded_at" in info

    async def test_list_ca_certs_returns_all_certs_sorted(self, manager, ca_dir, sample_ca):
        """Test 5: list_ca_certs returns all certs sorted by upload time desc."""
        _, _, cert_pem, key_pem = sample_ca
        await manager.upload_ca_cert(cert_pem, key_pem, label="first")

        cert2, key2, cert_pem2, key_pem2 = _generate_self_signed_ca(cn="Test CA 2")
        await manager.upload_ca_cert(cert_pem2.decode("utf-8"), key_pem2.decode("utf-8"), label="second")

        certs = await manager.list_ca_certs()
        assert len(certs) == 2
        assert certs[0]["label"] == "second"
        assert certs[1]["label"] == "first"

    async def test_upload_invalid_cert_raises_error(self, manager):
        """Test 6: Uploading invalid PEM raises CAManagerError."""
        with pytest.raises(CAManagerError, match="Invalid certificate"):
            await manager.upload_ca_cert(
                "not-a-cert",
                "not-a-key",
            )

    async def test_upload_mismatched_cert_key_raises_error(self, manager, sample_ca):
        """Test 7: Uploading cert with wrong key raises CAManagerError."""
        _, _, cert_pem, _ = sample_ca
        _, _, other_cert_pem, other_key_pem = _generate_self_signed_ca(cn="Other CA")

        with pytest.raises(CAManagerError, match="do not match"):
            await manager.upload_ca_cert(
                cert_pem,
                other_key_pem.decode("utf-8"),
            )

    async def test_reload_preserves_previous_on_failure(self, manager, ca_dir, sample_ca):
        """Test 8: reload with invalid cert preserves previous CA."""
        cert, _, cert_pem, key_pem = sample_ca
        await manager.upload_ca_cert(cert_pem, key_pem, label="original")
        original_serial = cert.serial_number

        with pytest.raises(CAManagerError):
            await manager.reload(
                cert_path="/nonexistent/bad.pem",
                key_path="/nonexistent/bad.key",
            )

        info = await manager.get_ca_info()
        assert info is not None
        assert info["serial"] == original_serial
        assert info["label"] == "original"
