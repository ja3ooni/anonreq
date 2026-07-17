"""Typed container for application state attached to FastAPI ``app.state``.

Provides:
- ``AppState`` dataclass with typed fields for every attribute stored on
  ``app.state`` during lifespan startup.
- ``get_app_state(app)`` helper for typed access from request handlers.
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
    from anonreq.deployment.modes import DeploymentConfig
    from anonreq.detection.presidio_client import PresidioClient
    from anonreq.discovery.admin_router import AssetInventory
    from anonreq.discovery.flow_analyzer import FlowAnalyzer
    from anonreq.discovery.hostname_allowlist import HostnameAllowlist
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
    from anonreq.trust_center.config import TrustCenterSettings
    from anonreq.trust_center.service import TrustCenterRateLimiter, TrustCenterService


@dataclass
class AppState:
    """Typed container for application state attached to FastAPI app."""

    # Core configuration
    settings: Settings | None = None

    # Secret management
    secret_volume_path: str | None = None
    secret_store: RuntimeSecretStore | None = None
    secret_rotation_buffer: SecretRotationBuffer | None = None
    secret_reloader: SecretVolumeReloader | None = None
    provider_registry: ProviderRegistry | None = None

    # Proxy / deployment
    proxy_mode: ProxyMode | None = None
    deployment_config: DeploymentConfig | None = None
    deployment_proxy: ReverseProxy | TransparentProxy | None = None

    # OIDC
    oidc_verifier: OIDCVerifier | None = None

    # Cache
    cache_manager: CacheManager | None = None

    # Routing
    alias_registry: AliasRegistry | None = None

    # Detection / anonymization
    presidio_client: PresidioClient | None = None
    pipeline: PipelineManager | None = None
    checksum_registry: ChecksumValidatorRegistry | None = None
    locale_registry: LocaleRegistry | None = None
    locale_negotiator: LocaleNegotiator | None = None
    recognizer_merger: RecognizerMerger | None = None
    preset_engine: PresetEngine | None = None
    active_compliance_presets: list[str] = field(default_factory=list)

    # Discovery / multimodal
    inventory_service: AssetInventory | None = None
    content_type_dispatcher: ContentTypeDispatcher | None = None

    # Policy engine
    pdp: PolicyDecisionPoint | None = None
    pep: PolicyEnforcementPoint | None = None
    forwarding_guard: ForwardingGuard | None = None
    policy_store: PolicyStore | None = None

    # TLS / MITM
    ca_manager: CAManager | None = None
    mitm_handler: MITMHandler | None = None

    # Audit / compliance
    audit_engine: AsyncEngine | None = None
    audit_chain: AuditChainService | None = None
    chain_anchor: ChainAnchorService | None = None
    slo_engine: SLOEngine | None = None
    webhook_client: httpx.AsyncClient | None = None
    breach_detector: BreachDetector | None = None
    compliance_evidence_service: ComplianceEvidenceService | None = None

    # Governance / oversight
    oversight_service: OversightService | None = None
    lifecycle_service: LifecycleService | None = None
    transparency_service: TransparencyService | None = None
    notification_service: NotificationService | None = None
    approval_manager: ApprovalManager | None = None

    # Gateway / AI detection
    gateway_status: GatewayStatus | None = None
    ai_detector: AIDetector | None = None
    route_table: RouteTable | None = None
    allowlist: HostnameAllowlist | None = None
    flow_analyzer: FlowAnalyzer | None = None
    pac_generator: PACGenerator | None = None
    mcp_inspector: MCPInspector | None = None

    # SOC / SIEM
    soc_normalizer: SOCNormalizer | None = None
    soc_mitre_mapper: MITREMapper | None = None
    soc_sink_router: Any = None
    soc_sink_health_monitor: Any = None

    # Trust Center
    trust_center_settings: TrustCenterSettings | None = None
    trust_center_enabled: bool = False
    trust_center_service: TrustCenterService | None = None
    trust_center_rate_limiter: TrustCenterRateLimiter | None = None

    # Internal cache (set dynamically, not part of public API)
    _cached_pre_provider_pipeline: PipelineManager | None = None

    # ForwardingGuard firewall pipeline
    firewall_pipeline: FirewallPipeline | None = None


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
        for fld in AppState.__dataclass_fields__:
            if fld.startswith("_"):
                continue
            raw_val = getattr(app.state, fld, _MISSING)
            if raw_val is not _MISSING:
                setattr(state, fld, raw_val)
        app.state._typed_app_state = state
    return state


def set_app_state(app: FastAPI, state: AppState) -> None:
    """Attach a pre-built ``AppState`` to the FastAPI application."""
    app.state._typed_app_state = state
