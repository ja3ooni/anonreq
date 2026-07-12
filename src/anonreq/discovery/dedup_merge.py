"""Dedup merge — cross-references DNS + proxy entries by hostname key.

Per D-001, D-014:
- DNS + proxy entries merged by matched provider
- Cross-reference by hostname key
- Timeline conflict resolution: latest last_seen wins
- Records keyed by (provider, hostname) tuple
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


class MergedRecord:
    """Unified record from merging DNS and proxy detections.

    Attributes:
        service_name: Primary service hostname.
        provider: Matched provider name, or None.
        sources: Detection sources — "dns", "proxy", or both.
        hostnames: List of observed hostnames.
        ip_addresses: List of observed IP addresses.
        first_seen: Earliest observation timestamp.
        last_seen: Most recent observation timestamp.
        total_requests: Total number of requests across sources.
        total_users: Number of distinct users/IPs.
        estimated_token_volume: Estimated total token count.
    """

    __slots__ = (
        "estimated_token_volume",
        "first_seen",
        "hostnames",
        "ip_addresses",
        "last_seen",
        "provider",
        "service_name",
        "sources",
        "total_requests",
        "total_users",
    )

    def __init__(
        self,
        service_name: str,
        provider: str | None,
        sources: list[str],
        hostnames: list[str],
        ip_addresses: list[str],
        first_seen: datetime,
        last_seen: datetime,
        total_requests: int,
        total_users: int,
        estimated_token_volume: int,
    ) -> None:
        self.service_name = service_name
        self.provider = provider
        self.sources = sources
        self.hostnames = hostnames
        self.ip_addresses = ip_addresses
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.total_requests = total_requests
        self.total_users = total_users
        self.estimated_token_volume = estimated_token_volume

    def __repr__(self) -> str:
        return (
            f"MergedRecord(provider={self.provider!r}, sources={self.sources!r}, "
            f"total_requests={self.total_requests})"
        )


class DedupMerge:
    """Cross-references DNS and proxy entries into unified discovery records."""

    def merge(
        self,
        dns_entries: list[DNSEntry],
        proxy_entries: list[ProxyEntry],
        matcher: HostnameMatcher,
    ) -> list[MergedRecord]:
        """Merge DNS and proxy entries into deduplicated discovery records.

        Args:
            dns_entries: List of DNS entries.
            proxy_entries: List of proxy entries.
            matcher: HostnameMatcher for provider identification.

        Returns:
            List of MergedRecord, deduplicated by (provider, hostname).
        """
        groups: dict[tuple[str | None, str], dict[str, Any]] = {}

        for entry in dns_entries:
            match = matcher.match(entry.hostname)
            if not match:
                continue
            key = (match.provider, entry.hostname)
            if key not in groups:
                groups[key] = {
                    "service_name": entry.hostname,
                    "provider": match.provider,
                    "sources": set(),
                    "hostnames": set(),
                    "ip_addresses": set(),
                    "first_seen": entry.timestamp,
                    "last_seen": entry.timestamp,
                    "total_requests": 0,
                    "users": set(),
                    "estimated_token_volume": 0,
                }
            g = groups[key]
            g["sources"].add("dns")
            g["hostnames"].add(entry.hostname)
            g["ip_addresses"].add(entry.source_ip)
            g["total_requests"] += 1
            g["users"].add(entry.source_ip)
            if entry.timestamp < g["first_seen"]:
                g["first_seen"] = entry.timestamp
            if entry.timestamp > g["last_seen"]:
                g["last_seen"] = entry.timestamp

        for entry in proxy_entries:
            hostname = urlparse(entry.url).hostname or ""
            match = matcher.match(hostname)
            if not match:
                continue
            key = (match.provider, hostname)
            if key not in groups:
                groups[key] = {
                    "service_name": hostname,
                    "provider": match.provider,
                    "sources": set(),
                    "hostnames": set(),
                    "ip_addresses": set(),
                    "first_seen": entry.timestamp,
                    "last_seen": entry.timestamp,
                    "total_requests": 0,
                    "users": set(),
                    "estimated_token_volume": 0,
                }
            g = groups[key]
            g["sources"].add("proxy")
            g["hostnames"].add(hostname)
            g["ip_addresses"].add(entry.source_ip)
            g["total_requests"] += 1
            g["users"].add(entry.source_ip)
            g["estimated_token_volume"] += entry.bytes // 4
            if entry.timestamp < g["first_seen"]:
                g["first_seen"] = entry.timestamp
            if entry.timestamp > g["last_seen"]:
                g["last_seen"] = entry.timestamp

        records: list[MergedRecord] = []
        for _key, info in groups.items():
            records.append(MergedRecord(
                service_name=info["service_name"],
                provider=info["provider"],
                sources=sorted(info["sources"]),
                hostnames=sorted(info["hostnames"]),
                ip_addresses=sorted(info["ip_addresses"]),
                first_seen=info["first_seen"],
                last_seen=info["last_seen"],
                total_requests=info["total_requests"],
                total_users=len(info["users"]),
                estimated_token_volume=info["estimated_token_volume"],
            ))

        records.sort(key=lambda r: r.last_seen, reverse=True)
        return records
