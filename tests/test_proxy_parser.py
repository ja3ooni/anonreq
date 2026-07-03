"""Tests for ProxyParser.

Per D-001, D-003:
- Supports Squid, Zscaler, and Palo Alto access log formats
- Invalid lines return None (skip, no error)
- Parser is read-only: no mutations from parsed content
"""

from __future__ import annotations

from datetime import datetime

import pytest

from anonreq.discovery.proxy_parser import ProxyParser, ProxyEntry


class TestProxyEntry:
    """Test ProxyEntry dataclass construction."""

    def test_proxy_entry_has_required_fields(self):
        """ProxyEntry contains source_ip, timestamp, method, url, status, bytes."""
        entry = ProxyEntry(
            source_ip="10.0.0.1",
            timestamp=datetime(2026, 6, 20, 10, 0, 0),
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            status=200,
            bytes=1500,
        )
        assert entry.source_ip == "10.0.0.1"
        assert entry.method == "POST"
        assert entry.url == "https://api.openai.com/v1/chat/completions"
        assert entry.status == 200
        assert entry.bytes == 1500

    def test_proxy_entry_with_optional_fields(self):
        """ProxyEntry accepts optional user_id, content_type, user_agent."""
        entry = ProxyEntry(
            source_ip="10.0.0.1",
            timestamp=datetime(2026, 6, 20, 10, 0, 0),
            method="GET",
            url="https://api.anthropic.com/v1/messages",
            status=200,
            bytes=500,
            user_id="user123",
            content_type="application/json",
            user_agent="Python/3.12",
        )
        assert entry.user_id == "user123"
        assert entry.content_type == "application/json"
        assert entry.user_agent == "Python/3.12"


class TestProxyParser:
    """Test suite for ProxyParser."""

    def setup_method(self):
        self.parser = ProxyParser()

    def test_parse_squid_format(self):
        """Parse Squid proxy access log format."""
        line = "1718870400.123    100 10.0.0.1 TCP_MISS/200 1500 POST https://api.openai.com/v1/chat/completions user123 DIRECT/104.18.1.1 application/json"
        entry = self.parser.parse_line(line, format="squid")
        assert entry is not None
        assert entry.source_ip == "10.0.0.1"
        assert entry.method == "POST"
        assert "api.openai.com" in entry.url
        assert entry.status == 200
        assert entry.bytes == 1500

    def test_parse_squid_without_user(self):
        """Parse Squid format without username (- placeholder)."""
        line = "1718870400.123    100 10.0.0.1 TCP_MISS/200 1500 GET https://api.anthropic.com/v1/messages - DIRECT/104.18.1.1 text/html"
        entry = self.parser.parse_line(line, format="squid")
        assert entry is not None
        assert entry.source_ip == "10.0.0.1"
        assert entry.method == "GET"
        assert "api.anthropic.com" in entry.url
        assert entry.status == 200

    def test_parse_zscaler_format(self):
        """Parse Zscaler proxy CSV log format."""
        line = "device123,06/20/2026 10:00:00,user@domain.com,Sales,https://api.groq.com/v1/chat/completions,Allowed,PolicyMatch,200,1500,application/json"
        entry = self.parser.parse_line(line, format="zscaler")
        assert entry is not None
        assert entry.source_ip == "device123"
        assert "api.groq.com" in entry.url
        assert entry.status == 200
        assert entry.bytes == 1500

    def test_parse_palo_alto_format(self):
        """Parse Palo Alto firewall log format."""
        line = "2026/06/20 10:00:00,001234567890,TRAFFIC,end,10.0.0.1,104.18.1.1,443,https://api.openai.com/v1/chat/completions,user@domain.com,ALLOW,1500"
        entry = self.parser.parse_line(line, format="paloalto")
        assert entry is not None
        assert entry.source_ip == "10.0.0.1"
        assert "api.openai.com" in entry.url
        assert entry.status == 200
        assert entry.bytes == 1500

    def test_auto_detect_squid(self):
        """Auto-detect Squid format by leading timestamp."""
        line = "1718870400.123    100 10.0.0.1 TCP_MISS/200 1500 POST https://api.openai.com/v1/chat/completions user123 DIRECT/104.18.1.1 application/json"
        entry = self.parser.parse_line(line)
        assert entry is not None
        assert entry.source_ip == "10.0.0.1"

    def test_auto_detect_zscaler(self):
        """Auto-detect Zscaler format by CSV pattern."""
        line = "device123,06/20/2026 10:00:00,user@domain.com,Sales,https://api.groq.com/v1/chat/completions,Allowed,PolicyMatch,200,1500,application/json"
        entry = self.parser.parse_line(line)
        assert entry is not None
        assert "api.groq.com" in entry.url

    def test_auto_detect_palo_alto(self):
        """Auto-detect Palo Alto format by leading date."""
        line = "2026/06/20 10:00:00,001234567890,TRAFFIC,end,10.0.0.1,104.18.1.1,443,https://api.openai.com/v1/chat/completions,user@domain.com,ALLOW,1500"
        entry = self.parser.parse_line(line)
        assert entry is not None
        assert "api.openai.com" in entry.url

    def test_invalid_line_returns_none(self):
        """Invalid log line returns None without raising."""
        entry = self.parser.parse_line("this is not a valid log line")
        assert entry is None

    def test_unknown_format_returns_none(self):
        """Unknown format string returns None."""
        entry = self.parser.parse_line("test", format="unknown")
        assert entry is None

    def test_empty_line_returns_none(self):
        """Empty line returns None."""
        assert self.parser.parse_line("") is None
        assert self.parser.parse_line("   ") is None

    def test_parse_batch_all_valid(self):
        """Batch parsing returns all valid entries."""
        lines = [
            "1718870400.123    100 10.0.0.1 TCP_MISS/200 1500 POST https://api.openai.com/v1/chat/completions user123 DIRECT/1.2.3.4 application/json",
            "1718870401.456    200 10.0.0.2 TCP_MISS/200 800 GET https://api.anthropic.com/v1/messages user456 DIRECT/1.2.3.5 application/json",
        ]
        entries = self.parser.parse_batch(lines)
        assert len(entries) == 2

    def test_parse_batch_skips_invalid(self):
        """Batch parsing skips invalid lines."""
        lines = [
            "1718870400.123    100 10.0.0.1 TCP_MISS/200 1500 POST https://api.openai.com/v1/chat/completions user123 DIRECT/1.2.3.4 application/json",
            "garbage line",
            "1718870401.456    200 10.0.0.2 TCP_MISS/200 800 GET https://api.anthropic.com/v1/messages user456 DIRECT/1.2.3.5 application/json",
        ]
        entries = self.parser.parse_batch(lines)
        assert len(entries) == 2
