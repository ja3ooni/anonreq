"""Discovery package — Shadow AI Detection pipeline.

Provides DNS log parsing, AI provider signature database, hostname matching,
proxy traffic parsing, usage analysis, event generation, and dedup merge.
"""

from anonreq.discovery.dns_parser import DNSParser, DNSEntry, DNSParseError
from anonreq.discovery.hostname_signatures import (
    ProviderSignature,
    AI_SIGNATURES,
    get_signature_by_hostname,
    get_signature_by_ip,
    add_custom_signature,
)
from anonreq.discovery.hostname_matcher import HostnameMatcher, MatchResult
from anonreq.discovery.proxy_parser import ProxyParser, ProxyEntry
from anonreq.discovery.usage_analyzer import UsageAnalyzer, UsageSummary
from anonreq.discovery.event_generator import EventGenerator, ShadowAIEvent
from anonreq.discovery.dedup_merge import DedupMerge, MergedRecord

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
    "MatchResult",
    "ProxyParser",
    "ProxyEntry",
    "UsageAnalyzer",
    "UsageSummary",
    "EventGenerator",
    "ShadowAIEvent",
    "DedupMerge",
    "MergedRecord",
]
