"""Tests for DedupMerge.

Per D-001, D-014:
- Merges DNS + proxy entries by hostname key
- Cross-references sources, combines counts, dedups users
- Timeline conflict resolution: latest last_seen wins
"""

from __future__ import annotations

from datetime import UTC, datetime

from anonreq.discovery.dedup_merge import DedupMerge, MergedRecord
from anonreq.discovery.dns_parser import DNSEntry
from anonreq.discovery.hostname_matcher import HostnameMatcher
from anonreq.discovery.hostname_signatures import AI_SIGNATURES
from anonreq.discovery.proxy_parser import ProxyEntry


class TestMergedRecord:
    """Test MergedRecord dataclass."""

    def test_merged_record_has_required_fields(self):
        """MergedRecord contains service_name, provider, sources, hostnames, etc."""
        ts = datetime.now(UTC)
        record = MergedRecord(
            service_name="api.openai.com",
            provider="openai",
            sources=["dns", "proxy"],
            hostnames=["api.openai.com"],
            ip_addresses=["10.0.0.1"],
            first_seen=ts,
            last_seen=ts,
            total_requests=100,
            total_users=5,
            estimated_token_volume=25000,
        )
        assert record.service_name == "api.openai.com"
        assert record.provider == "openai"
        assert record.sources == ["dns", "proxy"]
        assert record.total_requests == 100
        assert record.total_users == 5


class TestDedupMerge:
    """Test suite for DedupMerge."""

    def setup_method(self):
        self.matcher = HostnameMatcher(AI_SIGNATURES)
        self.merger = DedupMerge()

    def test_merge_dns_only(self):
        """Merge DNS-only entries returns correct grouped records."""
        entries = [
            DNSEntry("api.openai.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
            DNSEntry("api.openai.com", "10.0.0.2",
                     datetime(2026, 6, 20, 10, 1, 0, tzinfo=UTC)),
        ]
        records = self.merger.merge(entries, [], self.matcher)
        assert len(records) == 1
        assert records[0].provider == "openai"
        assert records[0].total_requests == 2
        assert records[0].total_users == 2
        assert "dns" in records[0].sources
        assert "proxy" not in records[0].sources

    def test_merge_proxy_only(self):
        """Merge proxy-only entries returns correct grouped records."""
        entries = [
            ProxyEntry("10.0.0.1",
                       datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC),
                       "POST", "https://api.openai.com/v1/chat/completions", 200, 1500),
        ]
        records = self.merger.merge([], entries, self.matcher)
        assert len(records) == 1
        assert records[0].provider == "openai"
        assert "proxy" in records[0].sources

    def test_merge_combined_sources(self):
        """Merge combines DNS and proxy entries for the same provider."""
        dns_entries = [
            DNSEntry("api.openai.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
        ]
        proxy_entries = [
            ProxyEntry("10.0.0.2",
                       datetime(2026, 6, 20, 10, 1, 0, tzinfo=UTC),
                       "POST", "https://api.openai.com/v1/chat/completions", 200, 1500),
        ]
        records = self.merger.merge(dns_entries, proxy_entries, self.matcher)
        assert len(records) == 1
        assert records[0].provider == "openai"
        assert "dns" in records[0].sources
        assert "proxy" in records[0].sources
        assert records[0].total_requests == 2
        assert records[0].total_users == 2

    def test_merge_multiple_providers(self):
        """Merge separates entries from different providers."""
        dns_entries = [
            DNSEntry("api.openai.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
            DNSEntry("api.anthropic.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
        ]
        records = self.merger.merge(dns_entries, [], self.matcher)
        assert len(records) == 2
        providers = {r.provider for r in records}
        assert providers == {"openai", "anthropic"}

    def test_timeline_conflict_latest_wins(self):
        """Timeline conflict resolution: latest timestamp wins."""
        dns_entries = [
            DNSEntry("api.openai.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
        ]
        proxy_entries = [
            ProxyEntry("10.0.0.1",
                       datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC),
                       "POST", "https://api.openai.com/v1/chat/completions", 200, 1500),
        ]
        records = self.merger.merge(dns_entries, proxy_entries, self.matcher)
        assert records[0].last_seen == datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        assert records[0].first_seen == datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)

    def test_unmatched_entries_are_excluded(self):
        """Entries that don't match any provider are excluded from results."""
        dns_entries = [
            DNSEntry("api.openai.com", "10.0.0.1",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
            DNSEntry("unknown.internal.corp", "10.0.0.2",
                     datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)),
        ]
        records = self.merger.merge(dns_entries, [], self.matcher)
        assert len(records) == 1
        assert records[0].provider == "openai"

    def test_empty_inputs(self):
        """Empty inputs return empty list."""
        records = self.merger.merge([], [], self.matcher)
        assert records == []
