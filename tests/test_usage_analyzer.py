"""Tests for UsageAnalyzer.

Per D-001, D-004:
- Groups entries by provider, computes aggregate stats
- Computes request_count, user_count (distinct source_ips), estimated_token_volume
- Merge combines DNS + proxy summaries
"""

from __future__ import annotations

from datetime import datetime, timezone

from anonreq.discovery.dns_parser import DNSEntry
from anonreq.discovery.hostname_matcher import HostnameMatcher, MatchResult
from anonreq.discovery.hostname_signatures import AI_SIGNATURES, ProviderSignature
from anonreq.discovery.proxy_parser import ProxyEntry
from anonreq.discovery.usage_analyzer import UsageAnalyzer, UsageSummary


class TestUsageSummary:
    """Test UsageSummary dataclass."""

    def test_usage_summary_fields(self):
        """UsageSummary contains service_name, request_count, user_count, etc."""
        ts = datetime.now(timezone.utc)
        summary = UsageSummary(
            service_name="api.openai.com",
            provider="openai",
            request_count=10,
            user_count=3,
            user_list=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
            first_seen=ts,
            last_seen=ts,
            estimated_token_volume=5000,
            data_classification=None,
        )
        assert summary.service_name == "api.openai.com"
        assert summary.provider == "openai"
        assert summary.request_count == 10
        assert summary.user_count == 3
        assert summary.estimated_token_volume == 5000


class TestUsageAnalyzer:
    """Test suite for UsageAnalyzer."""

    def setup_method(self):
        self.matcher = HostnameMatcher(AI_SIGNATURES)
        self.analyzer = UsageAnalyzer()

    def test_analyze_dns_groups_by_provider(self):
        """analyze_dns groups entries by matched provider."""
        entries = [
            DNSEntry("api.openai.com", "10.0.0.1", datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)),
            DNSEntry("api.anthropic.com", "10.0.0.1", datetime(2026, 6, 20, 10, 1, 0, tzinfo=timezone.utc)),
            DNSEntry("api.openai.com", "10.0.0.2", datetime(2026, 6, 20, 10, 2, 0, tzinfo=timezone.utc)),
        ]
        result = self.analyzer.analyze_dns(entries, self.matcher)
        assert "openai" in result
        assert "anthropic" in result
        assert result["openai"].request_count == 2
        assert result["openai"].user_count == 2
        assert result["anthropic"].request_count == 1

    def test_analyze_dns_deduplicates_users(self):
        """analyze_dns counts distinct source_ips."""
        entries = [
            DNSEntry("api.openai.com", "10.0.0.1", datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)),
            DNSEntry("api.openai.com", "10.0.0.1", datetime(2026, 6, 20, 10, 1, 0, tzinfo=timezone.utc)),
            DNSEntry("api.openai.com", "10.0.0.2", datetime(2026, 6, 20, 10, 2, 0, tzinfo=timezone.utc)),
        ]
        result = self.analyzer.analyze_dns(entries, self.matcher)
        assert result["openai"].user_count == 2
        assert len(result["openai"].user_list) == 2

    def test_analyze_dns_tracks_time_range(self):
        """analyze_dns tracks first_seen and last_seen."""
        entries = [
            DNSEntry("api.openai.com", "10.0.0.1", datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)),
            DNSEntry("api.openai.com", "10.0.0.1", datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)),
        ]
        result = self.analyzer.analyze_dns(entries, self.matcher)
        assert result["openai"].first_seen == datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)
        assert result["openai"].last_seen == datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)

    def test_analyze_proxy_groups_by_provider(self):
        """analyze_proxy groups proxy entries by matched provider."""
        entries = [
            ProxyEntry("10.0.0.1", datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc), "POST",
                       "https://api.openai.com/v1/chat/completions", 200, 1500),
            ProxyEntry("10.0.0.1", datetime(2026, 6, 20, 10, 1, 0, tzinfo=timezone.utc), "POST",
                       "https://api.anthropic.com/v1/messages", 200, 800),
        ]
        result = self.analyzer.analyze_proxy(entries, self.matcher)
        assert "openai" in result
        assert "anthropic" in result

    def test_analyze_proxy_token_volume(self):
        """analyze_proxy estimates token volume from bytes."""
        entries = [
            ProxyEntry("10.0.0.1", datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc), "POST",
                       "https://api.openai.com/v1/chat/completions", 200, 4000),
        ]
        result = self.analyzer.analyze_proxy(entries, self.matcher)
        assert result["openai"].estimated_token_volume == 1000  # bytes / 4

    def test_merge_summaries_combines_counts(self):
        """merge_summaries combines DNS and proxy counts."""
        ts = datetime.now(timezone.utc)
        dns_summaries = {
            "openai": UsageSummary("api.openai.com", "openai", 5, 2, ["10.0.0.1", "10.0.0.2"],
                                   ts, ts, 0, None),
        }
        proxy_summaries = {
            "openai": UsageSummary("api.openai.com", "openai", 10, 3,
                                   ["10.0.0.1", "10.0.0.3", "10.0.0.4"],
                                   ts, ts, 2000, None),
        }
        merged = self.analyzer.merge_summaries(dns_summaries, proxy_summaries)
        assert "openai" in merged
        assert merged["openai"].request_count == 15
        assert merged["openai"].user_count == 4
        assert merged["openai"].estimated_token_volume == 2000

    def test_merge_summaries_non_overlapping(self):
        """merge_summaries handles non-overlapping providers."""
        ts = datetime.now(timezone.utc)
        dns_summaries = {
            "openai": UsageSummary("api.openai.com", "openai", 5, 1, ["10.0.0.1"],
                                   ts, ts, 0, None),
        }
        proxy_summaries = {
            "anthropic": UsageSummary("api.anthropic.com", "anthropic", 3, 1, ["10.0.0.2"],
                                      ts, ts, 500, None),
        }
        merged = self.analyzer.merge_summaries(dns_summaries, proxy_summaries)
        assert "openai" in merged
        assert "anthropic" in merged
        assert merged["openai"].request_count == 5
        assert merged["anthropic"].request_count == 3
