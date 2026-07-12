"""Usage analysis — request count, users, tokens, and classification per service.

Per D-001, D-004:
- Groups entries by matched provider
- Computes request_count, user_count (distinct source_ips), estimated_token_volume
- Merge combines DNS + proxy summaries
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from anonreq.discovery.dns_parser import DNSEntry
from anonreq.discovery.hostname_matcher import HostnameMatcher
from anonreq.discovery.proxy_parser import ProxyEntry

logger = logging.getLogger(__name__)


class UsageSummary:
    """Aggregated usage summary for a single detected service.

    Attributes:
        service_name: The service hostname (e.g., api.openai.com).
        provider: Matched provider name (e.g., "openai"), or None if unknown.
        request_count: Total number of requests observed.
        user_count: Number of distinct source IPs.
        user_list: List of distinct source IPs.
        first_seen: Timestamp of the earliest observation.
        last_seen: Timestamp of the most recent observation.
        estimated_token_volume: Estimated token count (bytes / 4).
        data_classification: Data classification label, if available.
    """

    __slots__ = (
        "data_classification",
        "estimated_token_volume",
        "first_seen",
        "last_seen",
        "provider",
        "request_count",
        "service_name",
        "user_count",
        "user_list",
    )

    def __init__(
        self,
        service_name: str,
        provider: str | None,
        request_count: int,
        user_count: int,
        user_list: list[str],
        first_seen: datetime,
        last_seen: datetime,
        estimated_token_volume: int,
        data_classification: str | None,
    ) -> None:
        self.service_name = service_name
        self.provider = provider
        self.request_count = request_count
        self.user_count = user_count
        self.user_list = user_list
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.estimated_token_volume = estimated_token_volume
        self.data_classification = data_classification

    def __repr__(self) -> str:
        return (
            f"UsageSummary(provider={self.provider!r}, request_count={self.request_count}, "
            f"user_count={self.user_count})"
        )


class UsageAnalyzer:
    """Analyzes DNS and proxy entries to produce per-service usage summaries."""

    def analyze_dns(
        self,
        entries: list[DNSEntry],
        matcher: HostnameMatcher,
    ) -> dict[str, UsageSummary]:
        """Analyze DNS entries grouped by matched provider.

        Args:
            entries: List of DNS entries to analyze.
            matcher: HostnameMatcher for provider identification.

        Returns:
            Dict mapping provider name to UsageSummary.
        """
        groups: dict[str, dict[str, Any]] = {}

        for entry in entries:
            match = matcher.match(entry.hostname)
            provider = match.provider if match else "unknown"

            if provider not in groups:
                groups[provider] = {
                    "service_name": entry.hostname,
                    "provider": provider if match else None,
                    "request_count": 0,
                    "users": set(),
                    "first_seen": entry.timestamp,
                    "last_seen": entry.timestamp,
                    "estimated_token_volume": 0,
                    "data_classification": None,
                }

            g = groups[provider]
            g["request_count"] += 1
            g["users"].add(entry.source_ip)
            if entry.timestamp < g["first_seen"]:
                g["first_seen"] = entry.timestamp
            if entry.timestamp > g["last_seen"]:
                g["last_seen"] = entry.timestamp

        return {
            provider: UsageSummary(
                service_name=info["service_name"],
                provider=info["provider"],
                request_count=info["request_count"],
                user_count=len(info["users"]),
                user_list=sorted(info["users"]),
                first_seen=info["first_seen"],
                last_seen=info["last_seen"],
                estimated_token_volume=info["estimated_token_volume"],
                data_classification=info["data_classification"],
            )
            for provider, info in groups.items()
        }

    def analyze_proxy(
        self,
        entries: list[ProxyEntry],
        matcher: HostnameMatcher,
    ) -> dict[str, UsageSummary]:
        """Analyze proxy entries grouped by matched provider.

        Args:
            entries: List of proxy entries to analyze.
            matcher: HostnameMatcher for provider identification.

        Returns:
            Dict mapping provider name to UsageSummary.
        """
        groups: dict[str, dict[str, Any]] = {}

        for entry in entries:
            hostname = urlparse(entry.url).hostname or ""
            match = matcher.match(hostname)
            provider = match.provider if match else "unknown"

            if provider not in groups:
                groups[provider] = {
                    "service_name": hostname,
                    "provider": provider if match else None,
                    "request_count": 0,
                    "users": set(),
                    "first_seen": entry.timestamp,
                    "last_seen": entry.timestamp,
                    "estimated_token_volume": 0,
                    "data_classification": None,
                }

            g = groups[provider]
            g["request_count"] += 1
            g["users"].add(entry.source_ip)
            g["estimated_token_volume"] += entry.bytes // 4
            if entry.timestamp < g["first_seen"]:
                g["first_seen"] = entry.timestamp
            if entry.timestamp > g["last_seen"]:
                g["last_seen"] = entry.timestamp

        return {
            provider: UsageSummary(
                service_name=info["service_name"],
                provider=info["provider"],
                request_count=info["request_count"],
                user_count=len(info["users"]),
                user_list=sorted(info["users"]),
                first_seen=info["first_seen"],
                last_seen=info["last_seen"],
                estimated_token_volume=info["estimated_token_volume"],
                data_classification=info["data_classification"],
            )
            for provider, info in groups.items()
        }

    def merge_summaries(
        self,
        dns_summaries: dict[str, UsageSummary],
        proxy_summaries: dict[str, UsageSummary],
    ) -> dict[str, UsageSummary]:
        """Merge DNS and proxy summaries into a combined view.

        Combines counts, deduplicates users, keeps wider time range,
        and sums estimated token volume.

        Args:
            dns_summaries: Summaries from DNS analysis.
            proxy_summaries: Summaries from proxy analysis.

        Returns:
            Merged dict of provider name to UsageSummary.
        """
        all_providers = set(dns_summaries) | set(proxy_summaries)
        merged: dict[str, UsageSummary] = {}

        for provider in all_providers:
            dns = dns_summaries.get(provider)
            proxy = proxy_summaries.get(provider)

            if dns and proxy:
                all_users = list(set(dns.user_list) | set(proxy.user_list))
                merged[provider] = UsageSummary(
                    service_name=dns.service_name,
                    provider=provider,
                    request_count=dns.request_count + proxy.request_count,
                    user_count=len(all_users),
                    user_list=sorted(all_users),
                    first_seen=min(dns.first_seen, proxy.first_seen),
                    last_seen=max(dns.last_seen, proxy.last_seen),
                    estimated_token_volume=dns.estimated_token_volume + proxy.estimated_token_volume,  # noqa: E501
                    data_classification=dns.data_classification or proxy.data_classification,
                )
            elif dns:
                merged[provider] = dns
            elif proxy:
                merged[provider] = proxy

        return merged
