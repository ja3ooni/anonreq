"""Typed subsystem containers for application state.

Provides typed groupings for logically related state fields, plus
``AppState`` which composes them and maintains backward-compatible
flat attribute access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

_MISSING = object()

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncEngine

    from anonreq.auth.oidc import OIDCVerifier
    from anonreq.cache.manager import CacheManager
    from anonreq.compliance.engine import PresetEngine
    from anonreq.config import Settings
    from anonreq.deployment.modes import TopologyConfig as DeploymentConfig
    from anonreq.detection.presidio_client import PresidioClient
    from anonreq.discovery.flow_analyzer import FlowAnalyzer
    from anonreq.discovery.hostname_allowlist import HostnameAllowlist
    from anonreq.discovery.inventory import AssetInventory
    from anonreq.firewall.pipeline import FirewallPipeline
    from anonreq.gateway.detector import AIDetector
    from anonreq.gateway.passthrough import GatewayStatus
    from anonreq.gateway.router import RouteTable
    from anonreq.governance.approval import ApprovalManager
    from anonreq.locale.checksum import ChecksumValidatorRegistry
    from anonreq.locale.merger import RecognizerMerger
    from anonreq.locale.negotiator import LocaleNegotiator
    from anonreq.locale.registry import LocaleRegistry
    from anonreq.mcp.inspector import MCPInspector
    from anonreq.multimodal.dispatcher import ContentTypeDispatcher
    from anonreq.pipeline.manager import PipelineManager
    from anonreq.policy.forwarding_guard import ForwardingGuard
    from anonreq.policy.pdp import PolicyDecisionPoint
    from anonreq.policy.pep import PolicyEnforcementPoint
    from anonreq.policy.store import PolicyStore
    from anonreq.providers.registry import ProviderRegistry
    from anonreq.proxy.ca_manager import CAManager
    from anonreq.proxy.mitm_handler import MITMHandler
    from anonreq.proxy.modes import ProxyMode
    from anonreq.proxy.pac import PACGenerator
    from anonreq.proxy.reverse_proxy import ReverseProxy
    from anonreq.proxy.transparent_proxy import TransparentProxy
    from anonreq.routing.alias_registry import AliasRegistry
    from anonreq.secrets.reloader import SecretVolumeReloader
    from anonreq.secrets.rotation import SecretRotationBuffer
    from anonreq.secrets.store import RuntimeSecretStore
    from anonreq.services.audit_chain import AuditChainService
    from anonreq.services.breach_detector import BreachDetector
    from anonreq.services.chain_anchor import ChainAnchorService
    from anonreq.services.compliance_evidence import ComplianceEvidenceService
    from anonreq.services.lifecycle import LifecycleService
    from anonreq.services.notifications import NotificationService
    from anonreq.services.oversight import OversightService
    from anonreq.services.slo_engine import SLOEngine
    from anonreq.services.transparency import TransparencyService
    from anonreq.soc.mitre import MITREMapper
    from anonreq.soc.normalizer import SOCNormalizer
    from anonreq.tenant.registry import TenantRegistry
    from anonreq.trust_center.config import TrustCenterSettings
    from anonreq.trust_center.service import TrustCenterRateLimiter, TrustCenterService


# ── Subsystem dataclasses ────────────────────────────────────────────────────


@dataclass
class SecretState:
    """Secret management subsystem."""
    volume_path: str | None = None
    store: RuntimeSecretStore | None = None
    rotation_buffer: SecretRotationBuffer | None = None
    reloader: SecretVolumeReloader | None = None
    provider_registry: ProviderRegistry | None = None


@dataclass
class ProxyState:
    """Proxy / deployment subsystem."""
    mode: ProxyMode | None = None
    deployment_config: DeploymentConfig | None = None
    deployment_proxy: ReverseProxy | TransparentProxy | None = None
    ca_manager: CAManager | None = None
    mitm_handler: MITMHandler | None = None
    pac_generator: PACGenerator | None = None


@dataclass
class DetectionState:
    """Detection / anonymization subsystem."""
    presidio_client: PresidioClient | None = None
    pipeline: PipelineManager | None = None
    checksum_registry: ChecksumValidatorRegistry | None = None
    locale_registry: LocaleRegistry | None = None
    locale_negotiator: LocaleNegotiator | None = None
    recognizer_merger: RecognizerMerger | None = None
    preset_engine: PresetEngine | None = None
    active_compliance_presets: list[str] = field(default_factory=list)
    cached_pre_provider_pipeline: PipelineManager | None = None
    firewall_pipeline: FirewallPipeline | None = None


@dataclass
class PolicyState:
    """Policy engine subsystem."""
    pdp: PolicyDecisionPoint | None = None
    pep: PolicyEnforcementPoint | None = None
    forwarding_guard: ForwardingGuard | None = None
    policy_store: PolicyStore | None = None


@dataclass
class AuditState:
    """Audit / compliance subsystem."""
    engine: AsyncEngine | None = None
    chain: AuditChainService | None = None
    chain_anchor: ChainAnchorService | None = None
    slo_engine: SLOEngine | None = None
    webhook_client: httpx.AsyncClient | None = None
    breach_detector: BreachDetector | None = None
    evidence_service: ComplianceEvidenceService | None = None


@dataclass
class GovernanceState:
    """Governance / oversight subsystem."""
    oversight_service: OversightService | None = None
    lifecycle_service: LifecycleService | None = None
    transparency_service: TransparencyService | None = None
    notification_service: NotificationService | None = None
    approval_manager: ApprovalManager | None = None


@dataclass
class GatewayState:
    """Gateway / AI detection subsystem."""
    status: GatewayStatus | None = None
    ai_detector: AIDetector | None = None
    route_table: RouteTable | None = None
    allowlist: HostnameAllowlist | None = None
    flow_analyzer: FlowAnalyzer | None = None
    mcp_inspector: MCPInspector | None = None


@dataclass
class SOCState:
    """SOC / SIEM subsystem."""
    normalizer: SOCNormalizer | None = None
    mitre_mapper: MITREMapper | None = None
    sink_router: Any = None
    sink_health_monitor: Any = None


@dataclass
class TrustCenterState:
    """Trust Center subsystem."""
    settings: TrustCenterSettings | None = None
    enabled: bool = False
    service: TrustCenterService | None = None
    rate_limiter: TrustCenterRateLimiter | None = None


# ── Backward-compatible flat-name mapping ────────────────────────────────────
# Maps old flat field names to (subsystem_attr, field_name) for __getattr__.

_FLAT_MAP: dict[str, tuple[str, str]] = {
    # Secret management
    "secret_volume_path": ("secrets", "volume_path"),
    "secret_store": ("secrets", "store"),
    "secret_rotation_buffer": ("secrets", "rotation_buffer"),
    "secret_reloader": ("secrets", "reloader"),
    "provider_registry": ("secrets", "provider_registry"),
    # Proxy / deployment
    "proxy_mode": ("proxy", "mode"),
    "deployment_config": ("proxy", "deployment_config"),
    "deployment_proxy": ("proxy", "deployment_proxy"),
    "ca_manager": ("proxy", "ca_manager"),
    "mitm_handler": ("proxy", "mitm_handler"),
    "pac_generator": ("proxy", "pac_generator"),
    # Detection / anonymization
    "presidio_client": ("detection", "presidio_client"),
    "pipeline": ("detection", "pipeline"),
    "checksum_registry": ("detection", "checksum_registry"),
    "locale_registry": ("detection", "locale_registry"),
    "locale_negotiator": ("detection", "locale_negotiator"),
    "recognizer_merger": ("detection", "recognizer_merger"),
    "preset_engine": ("detection", "preset_engine"),
    "active_compliance_presets": ("detection", "active_compliance_presets"),
    "_cached_pre_provider_pipeline": ("detection", "cached_pre_provider_pipeline"),
    "firewall_pipeline": ("detection", "firewall_pipeline"),
    # Policy engine
    "pdp": ("policy", "pdp"),
    "pep": ("policy", "pep"),
    "forwarding_guard": ("policy", "forwarding_guard"),
    "policy_store": ("policy", "policy_store"),
    # Audit / compliance
    "audit_engine": ("audit", "engine"),
    "audit_chain": ("audit", "chain"),
    "chain_anchor": ("audit", "chain_anchor"),
    "slo_engine": ("audit", "slo_engine"),
    "webhook_client": ("audit", "webhook_client"),
    "breach_detector": ("audit", "breach_detector"),
    "compliance_evidence_service": ("audit", "evidence_service"),
    # Governance / oversight
    "oversight_service": ("governance", "oversight_service"),
    "lifecycle_service": ("governance", "lifecycle_service"),
    "transparency_service": ("governance", "transparency_service"),
    "notification_service": ("governance", "notification_service"),
    "approval_manager": ("governance", "approval_manager"),
    # Gateway / AI detection
    "gateway_status": ("gateway", "status"),
    "ai_detector": ("gateway", "ai_detector"),
    "route_table": ("gateway", "route_table"),
    "allowlist": ("gateway", "allowlist"),
    "flow_analyzer": ("gateway", "flow_analyzer"),
    "mcp_inspector": ("gateway", "mcp_inspector"),
    # SOC / SIEM
    "soc_normalizer": ("soc", "normalizer"),
    "soc_mitre_mapper": ("soc", "mitre_mapper"),
    "soc_sink_router": ("soc", "sink_router"),
    "soc_sink_health_monitor": ("soc", "sink_health_monitor"),
    # Trust Center
    "trust_center_settings": ("trust_center", "settings"),
    "trust_center_enabled": ("trust_center", "enabled"),
    "trust_center_service": ("trust_center", "service"),
    "trust_center_rate_limiter": ("trust_center", "rate_limiter"),
}

_DIRECT_FIELDS = frozenset({
    "settings", "oidc_verifier", "cache_manager",
    "tenant_registry", "alias_registry",
    "inventory_service", "content_type_dispatcher",
})


@dataclass
class AppState:
    """Typed container for application state attached to FastAPI app.

    Subsystem fields are accessible via typed attributes
    (``state.audit.engine``) and via backward-compatible flat names
    (``state.audit_engine``) through ``__getattr__``.
    """

    # Core configuration
    settings: Settings | None = None

    # OIDC
    oidc_verifier: OIDCVerifier | None = None

    # Cache
    cache_manager: CacheManager | None = None

    # Tenant registry
    tenant_registry: TenantRegistry | None = None

    # Routing
    alias_registry: AliasRegistry | None = None

    # Discovery / multimodal
    inventory_service: AssetInventory | None = None
    content_type_dispatcher: ContentTypeDispatcher | None = None

    # Subsystems
    secrets: SecretState = field(default_factory=SecretState)
    proxy: ProxyState = field(default_factory=ProxyState)
    detection: DetectionState = field(default_factory=DetectionState)
    policy: PolicyState = field(default_factory=PolicyState)
    audit: AuditState = field(default_factory=AuditState)
    governance: GovernanceState = field(default_factory=GovernanceState)
    gateway: GatewayState = field(default_factory=GatewayState)
    soc: SOCState = field(default_factory=SOCState)
    trust_center: TrustCenterState = field(default_factory=TrustCenterState)

    def __getattr__(self, name: str) -> Any:
        """Backward-compatible flat attribute access.

        Delegates to the appropriate subsystem for names in ``_FLAT_MAP``.
        Raises ``AttributeError`` for unknown names.
        """
        if name in _FLAT_MAP:
            subsystem_name, field_name = _FLAT_MAP[name]
            subsystem = object.__getattribute__(self, subsystem_name)
            return getattr(subsystem, field_name)
        raise AttributeError(f"'AppState' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Backward-compatible flat attribute setting."""
        if name in _FLAT_MAP:
            subsystem_name, field_name = _FLAT_MAP[name]
            subsystem = object.__getattribute__(self, subsystem_name)
            setattr(subsystem, field_name, value)
        else:
            object.__setattr__(self, name, value)


def get_app_state(app: FastAPI) -> AppState:
    """Return the typed ``AppState`` attached to the FastAPI application.

    Lazily initialises the dataclass on first access so that
    ``bootstrap_runtime_secrets`` (which runs before lifespan) can still
    set attributes on the raw ``app.state`` namespace.

    On first creation, any attributes already present on the raw
    ``app.state`` are copied into the new ``AppState`` instance so that
    test fixtures that set ``app.state.X`` directly continue to work.
    """
    state: AppState | None = getattr(app.state, "_typed_app_state", None)
    if state is None:
        state = AppState()
        # Sync raw attributes that tests / bootstrap already set
        for fld in _FLAT_MAP:
            raw_val = getattr(app.state, fld, _MISSING)
            if raw_val is not _MISSING:
                setattr(state, fld, raw_val)
        # Sync direct fields
        for fld in _DIRECT_FIELDS:
            raw_val = getattr(app.state, fld, _MISSING)
            if raw_val is not _MISSING:
                setattr(state, fld, raw_val)
        app.state._typed_app_state = state
    return state


def set_app_state(app: FastAPI, state: AppState) -> None:
    """Attach a pre-built ``AppState`` to the FastAPI application."""
    app.state._typed_app_state = state
