"""Tests for TLS termination and re-origination module."""

from __future__ import annotations

import ssl
import tempfile
from datetime import UTC
from pathlib import Path

import pytest

from anonreq.proxy.tls import (
    ConfigurationError,
    TLSInterceptor,
    create_tls_context,
)


def _generate_test_cert_pair(tmpdir: str) -> tuple[Path, Path]:
    """Generate a self-signed cert+key pair for testing."""
    from datetime import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Cert")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + 1))
        .sign(key, hashes.SHA256())
    )
    cert_path = Path(tmpdir) / "test-cert.pem"
    key_path = Path(tmpdir) / "test-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class TestTLSInterceptor:
    """Tests for the TLSInterceptor class."""

    def test_raises_without_ca_files(self):
        """Test 1: TLSInterceptor raises ConfigurationError without CA files."""
        with pytest.raises(ConfigurationError, match="CA certificate and key paths"):
            TLSInterceptor()

    def test_raises_with_none_paths(self):
        """Test 2: Passing None raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="required"):
            TLSInterceptor(ca_cert_path=None, ca_key_path=None)

    def test_raises_with_missing_files(self):
        """Test 3: Non-existent CA files raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="not found"):
            TLSInterceptor(
                ca_cert_path="/nonexistent/ca.pem",
                ca_key_path="/nonexistent/ca-key.pem",
            )

    def test_initializes_with_valid_ca_files(self):
        """Test 4: TLSInterceptor loads certs and creates contexts."""
        with tempfile.TemporaryDirectory() as tmp:
            cert_path, key_path = _generate_test_cert_pair(tmp)
            interceptor = TLSInterceptor(
                ca_cert_path=str(cert_path),
                ca_key_path=str(key_path),
            )
            assert interceptor.ca_cert_subject is not None
            assert interceptor.ca_cert_serial is not None
            assert interceptor.ca_cert_not_after is not None
            assert isinstance(interceptor.server_context, ssl.SSLContext)
            assert isinstance(interceptor.upstream_context, ssl.SSLContext)

    def test_server_context_check_hostname_false(self):
        """Test 5: Server context has check_hostname=False."""
        with tempfile.TemporaryDirectory() as tmp:
            cert_path, key_path = _generate_test_cert_pair(tmp)
            interceptor = TLSInterceptor(
                ca_cert_path=str(cert_path),
                ca_key_path=str(key_path),
            )
            assert interceptor.server_context.check_hostname is False

    def test_upstream_context_check_hostname_true(self):
        """Test 6: Upstream context has check_hostname=True."""
        with tempfile.TemporaryDirectory() as tmp:
            cert_path, key_path = _generate_test_cert_pair(tmp)
            interceptor = TLSInterceptor(
                ca_cert_path=str(cert_path),
                ca_key_path=str(key_path),
            )
            assert interceptor.upstream_context.check_hostname is True


class TestCertificatePinningDetection:
    """Tests for static certificate_pinning_detected method."""

    def test_empty_bytes_returns_false(self):
        """Empty DER bytes returns False (no exception)."""
        assert TLSInterceptor.certificate_pinning_detected(b"") is False

    def test_invalid_der_returns_false(self):
        """Invalid DER bytes returns False."""
        assert TLSInterceptor.certificate_pinning_detected(b"\x00\x01\x02") is False

    def test_random_bytes_returns_false(self):
        """Random non-cert bytes returns False."""
        assert TLSInterceptor.certificate_pinning_detected(b"not a cert at all") is False


class TestCreateTLSContext:
    """Tests for the create_tls_context factory function."""

    def test_returns_configured_ssl_context(self):
        """create_tls_context returns an SSLContext with secure settings."""
        with tempfile.TemporaryDirectory() as tmp:
            cert_path, key_path = _generate_test_cert_pair(tmp)
            ctx = create_tls_context(str(cert_path), str(key_path))
            assert isinstance(ctx, ssl.SSLContext)
            assert ctx.protocol == ssl.PROTOCOL_TLS_SERVER
            assert ctx.check_hostname is False
