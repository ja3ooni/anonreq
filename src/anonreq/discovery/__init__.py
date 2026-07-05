"""Discovery package — Shadow AI Detection pipeline.

Provides DNS log parsing, AI provider signature database, hostname matching,
proxy traffic parsing, usage analysis, event generation, dedup merge, AI
provider identification, and flow analysis heuristics.
"""

from anonreq.discovery.dns_parser import DNSParser, DNSEntry, DNSParseError
from anonreq.discovery.hostname_signatures import (
    ProviderSignature,
    AI_SIGNATURES,
    get_signature_by_hostname,
    get_signature_by_ip,
    add_custom_signature,
)
from anonreq.discovery.hostname_matcher import HostnameMatcher, MatchResult as HostnameMatcherResult
from anonreq.discovery.proxy_parser import ProxyParser, ProxyEntry
from anonreq.discovery.usage_analyzer import UsageAnalyzer, UsageSummary
from anonreq.discovery.event_generator import EventGenerator, ShadowAIEvent
from anonreq.discovery.dedup_merge import DedupMerge, MergedRecord
from anonreq.discovery.ai_signatures import (
    AI_PROVIDER_SIGNATURES,
    get_provider_by_hostname,
    get_provider_by_ip,
    get_provider_by_path,
)
from anonreq.discovery.hostname_allowlist import HostnameAllowlist, MatchResult
from anonreq.discovery.flow_analyzer import FlowAnalyzer, FlowResult

__all__ = [
    "DNSParser",
    "DNSEntry",
    "DNSParseError",
    "ProviderSignature",
    "AI_SIGNATURES",
    "get_signature_by_hostname",
    "get_signature_by_ip",
    "add_custom_signature",
    "HostnameMatcher",
    "HostnameMatcherResult",
    "ProxyParser",
    "ProxyEntry",
    "UsageAnalyzer",
    "UsageSummary",
    "EventGenerator",
    "ShadowAIEvent",
    "DedupMerge",
    "MergedRecord",
    "AI_PROVIDER_SIGNATURES",
    "get_provider_by_hostname",
    "get_provider_by_ip",
    "get_provider_by_path",
    "HostnameAllowlist",
    "MatchResult",
    "FlowAnalyzer",
    "FlowResult",
]
