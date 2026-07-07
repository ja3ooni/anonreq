from __future__ import annotations

import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from anonreq.proxy.tls_interceptor import TLSInterceptor, TLSInterceptorError


def _write_test_ca(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AnonReq Test CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "AnonReq Test Root"),
        ]
    )
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "ca.pem"
    key_path = tmp_path / "ca.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path, cert, key


@pytest.fixture
def interceptor(tmp_path):
    cert_path, key_path, cert, _key = _write_test_ca(tmp_path)
    return TLSInterceptor(str(cert_path), str(key_path)), cert


def test_tls_interceptor_generates_cert_with_domain_san(interceptor):
    tls, ca_cert = interceptor
    cert, _key = tls._generate_cert("api.openai.com", ca_cert, tls._ca_key)

    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "api.openai.com" in san.get_values_for_type(x509.DNSName)
    assert cert.issuer == ca_cert.subject


def test_generated_cert_is_signed_by_ca(interceptor):
    tls, ca_cert = interceptor
    cert, _key = tls._generate_cert("api.anthropic.com", ca_cert, tls._ca_key)

    ca_cert.public_key().verify(
        cert.signature,
        cert.tbs_certificate_bytes,
        padding.PKCS1v15(),
        cert.signature_hash_algorithm,
    )


@pytest.mark.asyncio
async def test_generate_cert_returns_tls13_ssl_context(interceptor):
    tls, _ca_cert = interceptor
    context = await tls.generate_cert("generativelanguage.googleapis.com")
    assert context.minimum_version.name == "TLSv1_3"


def test_multiple_domains_generate_different_leaf_certs(interceptor):
    tls, ca_cert = interceptor
    first, _ = tls._generate_cert("api.openai.com", ca_cert, tls._ca_key)
    second, _ = tls._generate_cert("api.anthropic.com", ca_cert, tls._ca_key)

    assert first.serial_number != second.serial_number
    first_san = first.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    second_san = second.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert first_san != second_san


def test_ca_cert_pem_exposes_loaded_ca(interceptor):
    tls, ca_cert = interceptor

    loaded = x509.load_pem_x509_certificate(tls.get_ca_cert_pem().encode("ascii"))
    assert loaded.serial_number == ca_cert.serial_number


def test_ca_load_failure_raises_configuration_error(tmp_path):
    cert_path = tmp_path / "missing.pem"
    key_path = tmp_path / "missing.key"

    with pytest.raises(TLSInterceptorError):
        TLSInterceptor(str(cert_path), str(key_path))


@pytest.mark.asyncio
async def test_health_check_reports_loadable_ca(interceptor):
    tls, _ca_cert = interceptor
    assert await tls.health_check() is True
