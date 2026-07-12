"""TLS termination and re-origination for the MITM proxy.

Provides:
- ``TLSInterceptor`` — manages CA-based TLS termination (client-facing)
  and re-origination (upstream-facing) SSL contexts.
- ``create_tls_context`` — factory function for server-side SSL contexts.
- ``certificate_pinning_detected`` — checks client certificates for
  pinning indicators.
"""

from __future__ import annotations

import ssl
from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from anonreq.exceptions import AnonReqError


class ConfigurationError(AnonReqError):
    """Raised when TLS configuration is invalid or missing."""

    def __init__(self, message: str = "TLS configuration error") -> None:
        super().__init__(
            message=message,
            error_type="configuration_error",
            status_code=500,
            code="tls_configuration_error",
        )


SECURE_CIPHERS = (
    "TLS_AES_256_GCM_SHA384:"
    "TLS_CHACHA20_POLY1305_SHA256:"
    "ECDHE-ECDSA-AES128-GCM-SHA256"
)


class TLSInterceptor:
    """Manages TLS termination and re-origination using a tenant CA.

    Creates a server-side ``SSLContext`` (``PROTOCOL_TLS_SERVER``) for
    terminating client TLS connections, and a client-side ``SSLContext``
    (``PROTOCOL_TLS_CLIENT``) for re-originating to upstream providers.

    Exposes CA metadata (subject, serial, expiry) for admin queries.
    """

    def __init__(
        self,
        ca_cert_path: str | None = None,
        ca_key_path: str | None = None,
    ) -> None:
        if not ca_cert_path or not ca_key_path:
            raise ConfigurationError(
                "CA certificate and key paths are required for TLS interception"
            )
        self._ca_cert_path = ca_cert_path
        self._ca_key_path = ca_key_path
        self._server_context: ssl.SSLContext | None = None
        self._upstream_context: ssl.SSLContext | None = None
        self._ca_cert: x509.Certificate | None = None

        self._load_ca()
        self._create_contexts()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def server_context(self) -> ssl.SSLContext:
        if self._server_context is None:
            raise ConfigurationError("Server context not initialized")
        return self._server_context

    @property
    def upstream_context(self) -> ssl.SSLContext:
        if self._upstream_context is None:
            raise ConfigurationError("Upstream context not initialized")
        return self._upstream_context

    @property
    def ca_cert(self) -> x509.Certificate | None:
        return self._ca_cert

    @property
    def ca_cert_subject(self) -> str | None:
        return self._ca_cert.subject.rfc4514_string() if self._ca_cert else None

    @property
    def ca_cert_serial(self) -> int | None:
        return self._ca_cert.serial_number if self._ca_cert else None

    @property
    def ca_cert_not_after(self) -> datetime | None:
        if self._ca_cert is None:
            return None
        try:
            return self._ca_cert.not_valid_after_utc
        except AttributeError:
            return self._ca_cert.not_valid_after

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_ca(self) -> None:
        """Load CA certificate and private key from PEM files."""
        cert_path = Path(self._ca_cert_path)
        key_path = Path(self._ca_key_path)

        if not cert_path.exists():
            raise ConfigurationError(f"CA certificate not found: {self._ca_cert_path}")
        if not key_path.exists():
            raise ConfigurationError(f"CA key not found: {self._ca_key_path}")

        cert_pem = cert_path.read_bytes()
        key_pem = key_path.read_bytes()

        self._ca_cert = x509.load_pem_x509_certificate(cert_pem)
        self._ca_key = load_pem_private_key(key_pem, password=None)

    def _create_contexts(self) -> None:
        """Create server-side and client-side SSL contexts."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self._ca_cert_path, self._ca_key_path)
        ctx.check_hostname = False
        ctx.set_ciphers(SECURE_CIPHERS)
        self._server_context = ctx

        upstream = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        upstream.check_hostname = True
        self._upstream_context = upstream

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload_ca(self, ca_cert_path: str, ca_key_path: str) -> None:
        """Replace CA certificate and key, then recreate SSL contexts."""
        self._ca_cert_path = ca_cert_path
        self._ca_key_path = ca_key_path
        self._load_ca()
        self._create_contexts()

    @staticmethod
    def certificate_pinning_detected(cert_der: bytes) -> bool:
        """Check whether a DER-encoded client certificate suggests pinning.

        Returns ``True`` if:
        - The public key is a short RSA key (≤1024 bits) or short EC key
          (≤192 bits).
        - The certificate cannot be parsed (defensive).

        Args:
            cert_der: DER-encoded X.509 certificate bytes.

        Returns:
            ``True`` when pinning indicators are present.
        """
        try:
            cert = x509.load_der_x509_certificate(cert_der)
        except Exception:
            return False

        pub_key = cert.public_key()

        if isinstance(pub_key, rsa.RSAPublicKey):
            if pub_key.key_size <= 1024:
                return True
        elif isinstance(pub_key, ec.EllipticCurvePublicKey) and pub_key.key_size is not None and pub_key.key_size <= 192:  # noqa
                return True

        return False


def create_tls_context(ca_cert_path: str, ca_key_path: str) -> ssl.SSLContext:
    """Create a server-side TLS context from PEM files.

    Args:
        ca_cert_path: Path to the PEM-encoded certificate.
        ca_key_path: Path to the PEM-encoded private key.

    Returns:
        A configured ``SSLContext`` with secure cipher suites.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ca_cert_path, ca_key_path)
    ctx.check_hostname = False
    ctx.set_ciphers(SECURE_CIPHERS)
    return ctx
