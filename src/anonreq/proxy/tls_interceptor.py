"""Dynamic TLS interception certificate generation.

This module implements the Phase 21 transparent proxy certificate path:
an enterprise-owned CA is loaded from disk and used to generate short-lived
leaf certificates for intercepted AI API domains. The generated certificates
are kept in memory only and returned as server-side ``SSLContext`` instances
for transparent proxy handshakes.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import ipaddress
import ssl
import tempfile
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.types import CertificateIssuerPrivateKeyTypes
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DEFAULT_CERT_TTL_SECONDS: Final[int] = 24 * 60 * 60
MIN_TLS_VERSION: Final[ssl.TLSVersion] = ssl.TLSVersion.TLSv1_3


class TLSInterceptorError(RuntimeError):
    """Raised when dynamic TLS certificate generation cannot proceed."""


def _load_cert(path: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(Path(path).read_bytes())
    except Exception as exc:
        raise TLSInterceptorError(f"failed to load CA certificate: {path}") from exc


def _load_key(path: str) -> CertificateIssuerPrivateKeyTypes:
    try:
        return serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    except Exception as exc:
        raise TLSInterceptorError(f"failed to load CA private key: {path}") from exc


def _domain_san(domain: str) -> x509.GeneralName:
    try:
        return x509.IPAddress(ipaddress.ip_address(domain))
    except ValueError:
        return x509.DNSName(domain)


def generate_dynamic_cert(
    domain: str,
    ca_cert: x509.Certificate,
    ca_key: CertificateIssuerPrivateKeyTypes,
    ttl_seconds: int = DEFAULT_CERT_TTL_SECONDS,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Generate a short-lived leaf certificate for an intercepted domain.

    Args:
        domain: SNI hostname or IP address from the intercepted TLS handshake.
        ca_cert: Enterprise CA certificate.
        ca_key: Enterprise CA private key used to sign the leaf certificate.
        ttl_seconds: Leaf certificate validity duration. Defaults to 24 hours.

    Returns:
        ``(certificate, private_key)`` for the generated leaf.
    """
    if not domain or any(ch.isspace() for ch in domain):
        raise TLSInterceptorError("domain must be a non-empty DNS name or IP address")
    if ttl_seconds <= 0:
        raise TLSInterceptorError("certificate TTL must be positive")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.UTC)
    serial = x509.random_serial_number()
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AnonReq Intercept"),
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(seconds=ttl_seconds))
        .add_extension(x509.SubjectAlternativeName([_domain_san(domain)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )
    return cert, key


class TLSInterceptor:
    """Create dynamic server TLS contexts from an enterprise CA."""

    def __init__(
        self,
        ca_cert_path: str,
        ca_key_path: str,
        cert_ttl_seconds: int = DEFAULT_CERT_TTL_SECONDS,
    ) -> None:
        self.ca_cert_path = ca_cert_path
        self.ca_key_path = ca_key_path
        self.cert_ttl_seconds = cert_ttl_seconds
        self._ca_cert = _load_cert(ca_cert_path)
        self._ca_key = _load_key(ca_key_path)
        self._context_cache: dict[str, ssl.SSLContext] = {}
        self._lock = asyncio.Lock()

    @property
    def ca_cert(self) -> x509.Certificate:
        """Loaded enterprise CA certificate."""
        return self._ca_cert

    async def generate_cert(self, domain: str) -> ssl.SSLContext:
        """Generate or return a cached TLS 1.3 server context for ``domain``."""
        async with self._lock:
            cached = self._context_cache.get(domain)
            if cached is not None:
                return cached

            cert, key = self._generate_cert(domain, self._ca_cert, self._ca_key)
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )

            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = MIN_TLS_VERSION
            context.check_hostname = False

            # SSLContext accepts paths only. Keep generated material in temp files
            # briefly, load it into OpenSSL, then remove it from disk.
            cert_file = tempfile.NamedTemporaryFile(prefix="anonreq-cert-", suffix=".pem", delete=False)  # noqa: E501, SIM115
            key_file = tempfile.NamedTemporaryFile(prefix="anonreq-key-", suffix=".pem", delete=False)  # noqa: E501, SIM115
            try:
                cert_file.write(cert_pem)
                key_file.write(key_pem)
                cert_file.close()
                key_file.close()
                context.load_cert_chain(certfile=cert_file.name, keyfile=key_file.name)
            finally:
                Path(cert_file.name).unlink(missing_ok=True)
                Path(key_file.name).unlink(missing_ok=True)

            self._context_cache[domain] = context
            return context

    def get_ca_cert_pem(self) -> str:
        """Return the enterprise CA certificate PEM for trust distribution."""
        return self._ca_cert.public_bytes(serialization.Encoding.PEM).decode("ascii")

    async def health_check(self) -> bool:
        """Verify the CA certificate and key are still loadable."""
        try:
            _load_cert(self.ca_cert_path)
            _load_key(self.ca_key_path)
        except TLSInterceptorError:
            return False
        return True

    def _generate_cert(
        self,
        domain: str,
        ca_cert: x509.Certificate,
        ca_key: CertificateIssuerPrivateKeyTypes,
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        return generate_dynamic_cert(
            domain=domain,
            ca_cert=ca_cert,
            ca_key=ca_key,
            ttl_seconds=self.cert_ttl_seconds,
        )
