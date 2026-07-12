"""Deployment mode abstraction for reverse, transparent, virtual, and physical appliances."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum


class DeploymentMode(StrEnum):
    REVERSE = "reverse"
    TRANSPARENT = "transparent"
    VIRTUAL = "virtual"
    PHYSICAL = "physical"


@dataclass(frozen=True)
class TopologyConfig:
    mode: DeploymentMode
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    tls_intercept_enabled: bool = False
    fail_open_policy: bool = False
    ca_cert_path: str = "/etc/anonreq/ca/cert.pem"
    ca_key_path: str = "/etc/anonreq/ca/key.pem"
    vm_spec: dict[str, object] | None = None
    physical_spec: dict[str, object] | None = None
    network_attachment: str = "reverse_proxy"
    extra: dict[str, object] = field(default_factory=dict)


def get_deployment_config(mode: str | None = None) -> TopologyConfig:
    raw = (mode or os.environ.get("DEPLOYMENT_MODE") or os.environ.get("ANONREQ_DEPLOYMENT_MODE") or "reverse")  # noqa: E501
    normalized = raw.strip().lower()
    try:
        deployment_mode = DeploymentMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DeploymentMode)
        raise ValueError(f"Unknown DEPLOYMENT_MODE '{raw}'. Valid modes: {valid}") from exc

    fail_open = _env_bool("ANONREQ_PROXY_FAIL_OPEN", default=False)
    ca_cert_path = os.environ.get("ANONREQ_CA_CERT_PATH", "/etc/anonreq/ca/cert.pem")
    ca_key_path = os.environ.get("ANONREQ_CA_KEY_PATH", "/etc/anonreq/ca/key.pem")

    if deployment_mode == DeploymentMode.REVERSE:
        return TopologyConfig(
            mode=deployment_mode,
            listen_port=int(os.environ.get("ANONREQ_REVERSE_PORT", "8080")),
            fail_open_policy=fail_open,
        )
    if deployment_mode == DeploymentMode.TRANSPARENT:
        return TopologyConfig(
            mode=deployment_mode,
            listen_port=int(os.environ.get("ANONREQ_TRANSPARENT_PORT", "8443")),
            tls_intercept_enabled=True,
            fail_open_policy=fail_open,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            network_attachment="dns_iptables_ebpf",
        )
    if deployment_mode == DeploymentMode.VIRTUAL:
        return TopologyConfig(
            mode=deployment_mode,
            listen_port=int(os.environ.get("ANONREQ_TRANSPARENT_PORT", "8443")),
            tls_intercept_enabled=True,
            fail_open_policy=fail_open,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            network_attachment="virtual_appliance",
            vm_spec={"vcpu": 4, "ram_gb": 16, "disk_gb": 100, "hypervisors": ["vmware", "hyper-v", "kvm"]},  # noqa: E501
        )
    return TopologyConfig(
        mode=deployment_mode,
        listen_port=int(os.environ.get("ANONREQ_TRANSPARENT_PORT", "8443")),
        tls_intercept_enabled=True,
        fail_open_policy=fail_open,
        ca_cert_path=ca_cert_path,
        ca_key_path=ca_key_path,
        network_attachment="physical_appliance",
        physical_spec={"nic_bonding": True, "hsm": "pkcs11", "air_gap_supported": True},
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
