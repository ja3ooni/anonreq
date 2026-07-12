"""Discovery package — Shadow AI Detection pipeline.

Provides DNS log parsing, AI provider signature database, hostname matching,
proxy traffic parsing, usage analysis, event generation, dedup merge, AI
provider identification, and flow analysis heuristics.
"""

from anonreq.discovery.ai_signatures import (
    AI_PROVIDER_SIGNATURES,
    get_provider_by_hostname,
    get_provider_by_ip,
    get_provider_by_path,
)
from anonreq.discovery.dedup_merge import DedupMerge, MergedRecord
from anonreq.discovery.dns_parser import DNSEntry, DNSParseError, DNSParser
from anonreq.discovery.event_generator import EventGenerator, ShadowAIEvent
from anonreq.discovery.flow_analyzer import FlowAnalyzer, FlowResult
from anonreq.discovery.hostname_allowlist import HostnameAllowlist, MatchResult
from anonreq.discovery.hostname_matcher import HostnameMatcher
from anonreq.discovery.hostname_matcher import MatchResult as HostnameMatcherResult
from anonreq.discovery.hostname_signatures import (
    AI_SIGNATURES,
    ProviderSignature,
    add_custom_signature,
    get_signature_by_hostname,
    get_signature_by_ip,
)
from anonreq.discovery.proxy_parser import ProxyEntry, ProxyParser
from anonreq.discovery.usage_analyzer import UsageAnalyzer, UsageSummary

__all__ = [
    "AI_PROVIDER_SIGNATURES",
    "AI_SIGNATURES",
    "DNSEntry",
    "DNSParseError",
    "DNSParser",
    "DedupMerge",
    "EventGenerator",
    "FlowAnalyzer",
    "FlowResult",
    "HostnameAllowlist",
    "HostnameMatcher",
    "HostnameMatcherResult",
    "MatchResult",
    "MergedRecord",
    "ProviderSignature",
    "ProxyEntry",
    "ProxyParser",
    "ShadowAIEvent",
    "UsageAnalyzer",
    "UsageSummary",
    "add_custom_signature",
    "get_provider_by_hostname",
    "get_provider_by_ip",
    "get_provider_by_path",
    "get_signature_by_hostname",
    "get_signature_by_ip",
]
