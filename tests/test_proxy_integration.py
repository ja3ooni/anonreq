from __future__ import annotations

import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from anonreq.deployment.modes import DeploymentMode, get_deployment_config
from anonreq.main import create_deployment_proxy
from anonreq.proxy.reverse_proxy import ReverseProxy, ReverseProxyRequest
from anonreq.proxy.transparent_proxy import ProxyRequest, TransparentProxy


class DummyDispatcher:
    async def dispatch(self, _content_type: str, body: bytes, ctx: object = None, **kwargs):
        return b"ok:" + body


def _write_test_ca(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AnonReq Integration CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "AnonReq Integration Root"),
        ]
    )
    now = dt.datetime.now(dt.UTC)
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
    return cert_path, key_path


def test_deployment_mode_reverse_defaults(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "reverse")

    config = get_deployment_config()

    assert config.mode == DeploymentMode.REVERSE
    assert config.listen_port == 8080
    assert config.tls_intercept_enabled is False


def test_deployment_mode_transparent_defaults(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "transparent")

    config = get_deployment_config()

    assert config.mode == DeploymentMode.TRANSPARENT
    assert config.listen_port == 8443
    assert config.tls_intercept_enabled is True


def test_deployment_mode_virtual_defaults(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "virtual")

    config = get_deployment_config()

    assert config.mode == DeploymentMode.VIRTUAL
    assert config.vm_spec["vcpu"] == 4
    assert config.network_attachment == "virtual_appliance"


def test_deployment_mode_physical_defaults(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "physical")

    config = get_deployment_config()

    assert config.mode == DeploymentMode.PHYSICAL
    assert config.physical_spec["hsm"] == "pkcs11"
    assert config.network_attachment == "physical_appliance"


def test_unknown_deployment_mode_raises_startup_error():
    with pytest.raises(ValueError, match="Unknown DEPLOYMENT_MODE"):
        get_deployment_config("sideways")


@pytest.mark.asyncio
async def test_reverse_proxy_handles_connect_tunneling():
    proxy = ReverseProxy(DummyDispatcher())

    response = await proxy.handle(ReverseProxyRequest(method="CONNECT", path="api.openai.com:443"))

    assert response.status_code == 200
    assert response.connect_tunnel is True
    assert response.headers["x-anonreq-connect-target"] == "api.openai.com:443"


@pytest.mark.asyncio
async def test_reverse_proxy_supports_base_url_rewrite_and_dispatch():
    proxy = ReverseProxy(DummyDispatcher(), upstream_base_url="https://api.anthropic.com")

    response = await proxy.handle(
        ReverseProxyRequest(
            method="POST",
            path="/v1/messages",
            headers={"Host": "anonreq.local", "Content-Type": "application/json"},
            body=b"{}",
        )
    )

    assert response.status_code == 200
    assert response.body == b"ok:{}"
    assert response.upstream_url == "https://api.anthropic.com/v1/messages"
    assert response.headers["host"] == "anonreq.local"


def test_create_deployment_proxy_reverse():
    config = get_deployment_config("reverse")

    proxy = create_deployment_proxy(config, DummyDispatcher())

    assert isinstance(proxy, ReverseProxy)


def test_create_deployment_proxy_transparent(tmp_path, monkeypatch):
    cert_path, key_path = _write_test_ca(tmp_path)
    monkeypatch.setenv("ANONREQ_CA_CERT_PATH", str(cert_path))
    monkeypatch.setenv("ANONREQ_CA_KEY_PATH", str(key_path))
    config = get_deployment_config("transparent")

    proxy = create_deployment_proxy(config, DummyDispatcher())

    assert isinstance(proxy, TransparentProxy)


@pytest.mark.asyncio
async def test_transparent_to_dispatcher_flow(tmp_path, monkeypatch):
    cert_path, key_path = _write_test_ca(tmp_path)
    monkeypatch.setenv("ANONREQ_CA_CERT_PATH", str(cert_path))
    monkeypatch.setenv("ANONREQ_CA_KEY_PATH", str(key_path))
    proxy = create_deployment_proxy(get_deployment_config("transparent"), DummyDispatcher())

    response = await proxy.handle_request(
        ProxyRequest(
            method="POST",
            host="api.openai.com",
            path="/v1/chat/completions",
            headers={"content-type": "application/json"},
            body=b"{}",
            client_hello=b"api.openai.com",
        )
    )

    assert response.status_code == 200
    assert response.routed_to_dispatcher is True
    assert response.body == b"ok:{}"
