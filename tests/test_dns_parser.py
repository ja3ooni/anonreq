"""Tests for DNSParser and DNSEntry.

Per D-001, D-002:
- DNS log parser supports syslog, JSON, and raw-text input formats
- Invalid log lines raise DNSParseError for single-line parse
- Batch parsing skips malformed lines safely
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.discovery.dns_parser import DNSParser, DNSEntry, DNSParseError
from anonreq.discovery.hostname_signatures import (
    AI_SIGNATURES,
    ProviderSignature,
    get_signature_by_hostname,
    get_signature_by_ip,
    add_custom_signature,
)


# ---------------------------------------------------------------------------
# DNSEntry construction
# ---------------------------------------------------------------------------


class TestDNSEntry:
    """Test DNSEntry dataclass construction."""

    def test_dns_entry_has_required_fields(self):
        """DNSEntry contains hostname, source_ip, timestamp, query_type."""
        ts = datetime.now(timezone.utc)
        entry = DNSEntry(
            hostname="api.openai.com",
            source_ip="10.0.0.1",
            timestamp=ts,
            query_type="A",
        )
        assert entry.hostname == "api.openai.com"
        assert entry.source_ip == "10.0.0.1"
        assert entry.timestamp == ts
        assert entry.query_type == "A"

    def test_dns_entry_with_optional_fields(self):
        """DNSEntry accepts optional response_ip and raw fields."""
        ts = datetime.now(timezone.utc)
        entry = DNSEntry(
            hostname="api.openai.com",
            source_ip="10.0.0.1",
            timestamp=ts,
            query_type="AAAA",
            response_ip="1.2.3.4",
            raw="raw line",
        )
        assert entry.response_ip == "1.2.3.4"
        assert entry.raw == "raw line"


# ---------------------------------------------------------------------------
# DNSParser — parse_line
# ---------------------------------------------------------------------------


class TestDNSParserParseLine:
    """Test DNSParser single-line parsing."""

    def test_parse_syslog_format(self):
        """Parse syslog-format DNS log entry."""
        line = "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A"
        parser = DNSParser()
        entry = parser.parse_line(line, format="syslog")
        assert entry.hostname == "api.openai.com"
        assert entry.source_ip == "10.0.0.1"
        assert entry.query_type == "A"
        assert entry.timestamp is not None

    def test_parse_json_format(self):
        """Parse JSON-format DNS log entry."""
        line = '{"timestamp": "2026-06-20T10:00:00Z", "src_ip": "10.0.0.1", "query": "api.openai.com", "qtype": "A"}'
        parser = DNSParser()
        entry = parser.parse_line(line, format="json")
        assert entry.hostname == "api.openai.com"
        assert entry.source_ip == "10.0.0.1"
        assert entry.query_type == "A"
        assert entry.timestamp is not None

    def test_parse_json_with_response_ip(self):
        """Parse JSON with optional response_ip field."""
        line = '{"timestamp": "2026-06-20T10:00:00Z", "src_ip": "10.0.0.1", "query": "api.openai.com", "qtype": "A", "response_ip": "1.2.3.4"}'
        parser = DNSParser()
        entry = parser.parse_line(line, format="json")
        assert entry.response_ip == "1.2.3.4"

    def test_parse_raw_format(self):
        """Parse raw-text DNS log entry (hostname per line)."""
        line = "api.openai.com"
        parser = DNSParser()
        entry = parser.parse_line(line, format="raw")
        assert entry.hostname == "api.openai.com"
        assert entry.query_type == "A"
        # raw format stamps with current time, source_ip from config
        assert entry.timestamp is not None

    def test_auto_detect_syslog(self):
        """Auto-detect syslog format by regex heuristics."""
        line = "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A"
        parser = DNSParser()
        entry = parser.parse_line(line)
        assert entry.hostname == "api.openai.com"
        assert entry.source_ip == "10.0.0.1"

    def test_auto_detect_json(self):
        """Auto-detect JSON format by leading brace."""
        line = '{"timestamp": "2026-06-20T10:00:00Z", "src_ip": "10.0.0.1", "query": "api.openai.com", "qtype": "A"}'
        parser = DNSParser()
        entry = parser.parse_line(line)
        assert entry.hostname == "api.openai.com"
        assert entry.source_ip == "10.0.0.1"

    def test_auto_detect_raw(self):
        """Auto-detect raw format for plain hostname lines."""
        line = "api.openai.com"
        parser = DNSParser()
        entry = parser.parse_line(line)
        assert entry.hostname == "api.openai.com"

    def test_invalid_line_raises_error(self):
        """Invalid log line raises DNSParseError."""
        parser = DNSParser()
        with pytest.raises(DNSParseError):
            parser.parse_line("this is not a valid log line")

    def test_invalid_json_raises_error(self):
        """Malformed JSON raises DNSParseError."""
        parser = DNSParser()
        with pytest.raises(DNSParseError):
            parser.parse_line('{"timestamp": "invalid', format="json")

    def test_invalid_syslog_raises_error(self):
        """Malformed syslog line raises DNSParseError."""
        parser = DNSParser()
        with pytest.raises(DNSParseError):
            parser.parse_line("random garbage line", format="syslog")

    def test_unknown_format_raises_error(self):
        """Unknown format string raises DNSParseError."""
        parser = DNSParser()
        with pytest.raises(DNSParseError, match="Unknown format"):
            parser.parse_line("test", format="unknown")


# ---------------------------------------------------------------------------
# DNSParser — parse_batch
# ---------------------------------------------------------------------------


class TestDNSParserParseBatch:
    """Test DNSParser batch parsing."""

    def test_batch_all_valid(self):
        """Batch parsing returns correct entry count for all-valid input."""
        lines = [
            "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A",
            "Jun 20 10:00:01 dns1 named[123]: 10.0.0.2 query: api.anthropic.com IN A",
            "Jun 20 10:00:02 dns1 named[123]: 10.0.0.3 query: api.groq.com IN A",
        ]
        parser = DNSParser()
        entries = parser.parse_batch(lines)
        assert len(entries) == 3
        assert entries[0].hostname == "api.openai.com"
        assert entries[1].hostname == "api.anthropic.com"
        assert entries[2].hostname == "api.groq.com"

    def test_batch_skips_invalid_lines(self):
        """Batch parsing skips malformed lines and returns valid ones."""
        lines = [
            "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A",
            "this is garbage",
            "Jun 20 10:00:02 dns1 named[123]: 10.0.0.3 query: api.groq.com IN A",
        ]
        parser = DNSParser()
        entries = parser.parse_batch(lines)
        assert len(entries) == 2

    def test_batch_all_invalid(self):
        """Batch parsing returns empty list for all-invalid input."""
        lines = ["garbage1", "garbage2", "garbage3"]
        parser = DNSParser()
        entries = parser.parse_batch(lines)
        assert entries == []

    def test_batch_empty(self):
        """Batch parsing returns empty list for empty input."""
        parser = DNSParser()
        entries = parser.parse_batch([])
        assert entries == []

    def test_batch_mixed_formats(self):
        """Batch parsing handles mixed formats (auto-detect per line)."""
        lines = [
            "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A",
            '{"timestamp": "2026-06-20T10:00:01Z", "src_ip": "10.0.0.2", "query": "api.anthropic.com", "qtype": "A"}',
            "api.deepseek.com",
        ]
        parser = DNSParser()
        entries = parser.parse_batch(lines)
        assert len(entries) == 3
        assert entries[0].hostname == "api.openai.com"
        assert entries[1].hostname == "api.anthropic.com"
        assert entries[2].hostname == "api.deepseek.com"

    def test_batch_with_format_override_syslog(self):
        """Batch parsing respects explicit syslog format override."""
        lines = [
            "Jun 20 10:00:00 dns1 named[123]: 10.0.0.1 query: api.openai.com IN A",
            "Jun 20 10:00:01 dns1 named[123]: 10.0.0.2 query: api.anthropic.com IN A",
        ]
        parser = DNSParser()
        entries = parser.parse_batch(lines, format="syslog")
        assert len(entries) == 2

    def test_batch_with_format_override_json(self):
        """Batch parsing respects explicit json format override."""
        lines = [
            '{"timestamp": "2026-06-20T10:00:00Z", "src_ip": "10.0.0.1", "query": "api.openai.com", "qtype": "A"}',
            '{"timestamp": "2026-06-20T10:00:01Z", "src_ip": "10.0.0.2", "query": "api.anthropic.com", "qtype": "A"}',
        ]
        parser = DNSParser()
        entries = parser.parse_batch(lines, format="json")
        assert len(entries) == 2

    def test_batch_max_size(self):
        """Batch parsing respects max_batch_size limit."""
        lines = [f"host{i}.example.com" for i in range(100)]
        parser = DNSParser(max_batch_size=50)
        entries = parser.parse_batch(lines)
        assert len(entries) == 50


# ---------------------------------------------------------------------------
# AI_SIGNATURES tests
# ---------------------------------------------------------------------------


class TestAISignatures:
    """Test AI provider signature database."""

    def test_signatures_contains_15_plus_providers(self):
        """AI_SIGNATURES contains 15+ providers with hostnames and IP ranges."""
        assert len(AI_SIGNATURES) >= 15
        for sig in AI_SIGNATURES:
            assert len(sig.hostnames) >= 1
            assert sig.provider
            assert sig.tier in ("major", "regional", "unknown")
            assert sig.jurisdiction

    def test_signature_has_required_fields(self):
        """ProviderSignature has all required fields."""
        sig = ProviderSignature(
            provider="test_provider",
            hostnames=["*.test.com"],
            ip_ranges=["10.0.0.0/8"],
            tier="major",
            jurisdiction="us",
        )
        assert sig.provider == "test_provider"
        assert sig.hostnames == ["*.test.com"]
        assert sig.ip_ranges == ["10.0.0.0/8"]
        assert sig.tier == "major"
        assert sig.jurisdiction == "us"

    def test_get_signature_by_hostname_exact(self):
        """get_signature_by_hostname finds provider by exact hostname match."""
        sig = get_signature_by_hostname("api.openai.com")
        assert sig is not None
        assert sig.provider == "openai"

    def test_get_signature_by_hostname_wildcard(self):
        """get_signature_by_hostname matches wildcard patterns."""
        sig = get_signature_by_hostname("some.random.openai.com")
        assert sig is not None
        assert sig.provider == "openai"

    def test_get_signature_by_hostname_no_match(self):
        """get_signature_by_hostname returns None for unknown hostnames."""
        sig = get_signature_by_hostname("nonexistent.example.com")
        assert sig is None

    def test_get_signature_by_ip_cidr(self):
        """get_signature_by_ip matches CIDR ranges."""
        sig = get_signature_by_ip("104.18.1.1")
        assert sig is not None
        assert sig.provider in ("openai", "anthropic", "perplexity", "xai", "groq")

    def test_get_signature_by_ip_no_match(self):
        """get_signature_by_ip returns None for unknown IPs."""
        sig = get_signature_by_ip("1.1.1.1")
        assert sig is None

    def test_get_signature_by_ip_invalid(self):
        """get_signature_by_ip returns None for invalid IP strings."""
        sig = get_signature_by_ip("not_an_ip")
        assert sig is None

    def test_add_custom_signature(self):
        """add_custom_signature registers runtime provider."""
        sig = ProviderSignature(
            provider="custom_provider",
            hostnames=["custom.api.com"],
            tier="unknown",
            jurisdiction="other",
        )
        add_custom_signature(sig)
        found = get_signature_by_hostname("custom.api.com")
        assert found is not None
        assert found.provider == "custom_provider"
