"""DNS log parser supporting syslog, JSON, and raw-text input formats.

Per D-001:
- Syslog format: parses BIND/Infoblox DNS query logs
- JSON format: structured DNS log entries
- Raw format: simple hostname-per-line
- Parser is read-only: no mutations from parsed content
- Invalid single lines raise DNSParseError; batch parsing skips malformed lines
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SYSLOG_RE = re.compile(
    r"(\w{3}\s+\d+\s+\d+:\d+:\d+)\s+\S+\s+\S+:\s+(\S+)\s+query:\s+(\S+)\s+IN\s+(\S+)"
)
_SYSLOG_TIMESTAMP_FMT = "%b %d %H:%M:%S"

_RAW_MAX_LINE_LENGTH = 4096
_DEFAULT_MAX_BATCH_SIZE = 10_000
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$")


class DNSParseError(ValueError):
    """Raised when a single DNS log line cannot be parsed."""


class DNSEntry:
    """Represents a parsed DNS query entry.

    Attributes:
        hostname: The queried hostname (fully qualified).
        source_ip: IP address of the client making the query.
        timestamp: When the query occurred.
        query_type: DNS record type (A, AAAA, CNAME, etc.).
        response_ip: Resolved IP address, if available.
        raw: Original log line for debugging.
    """

    __slots__ = ("hostname", "source_ip", "timestamp", "query_type", "response_ip", "raw")

    def __init__(
        self,
        hostname: str,
        source_ip: str,
        timestamp: datetime,
        query_type: str = "A",
        response_ip: str | None = None,
        raw: str | None = None,
    ) -> None:
        self.hostname = hostname
        self.source_ip = source_ip
        self.timestamp = timestamp
        self.query_type = query_type
        self.response_ip = response_ip
        self.raw = raw

    def __repr__(self) -> str:
        return (
            f"DNSEntry(hostname={self.hostname!r}, source_ip={self.source_ip!r}, "
            f"timestamp={self.timestamp!r}, query_type={self.query_type!r})"
        )


class DNSParser:
    """Parses DNS log lines from multiple input formats.

    Args:
        max_batch_size: Maximum number of lines to parse in a single batch.
            Defaults to 10,000. Additional lines beyond this limit are skipped.
    """

    def __init__(self, max_batch_size: int = _DEFAULT_MAX_BATCH_SIZE) -> None:
        self._max_batch_size = max_batch_size

    def parse_line(self, line: str, format: str = "auto") -> DNSEntry:
        """Parse a single DNS log line into a DNSEntry.

        Args:
            line: The log line to parse.
            format: One of "auto", "syslog", "json", or "raw".
                "auto" detects the format via heuristics.

        Returns:
            A DNSEntry with parsed fields.

        Raises:
            DNSParseError: If the line cannot be parsed in the given format.
        """
        if not line or len(line) > _RAW_MAX_LINE_LENGTH:
            raise DNSParseError("Empty or oversized log line")

        stripped = line.strip()

        if format == "auto":
            format = self._detect_format(stripped)

        if format == "syslog":
            return self._parse_syslog(stripped)
        elif format == "json":
            return self._parse_json(stripped)
        elif format == "raw":
            return self._parse_raw(stripped)
        else:
            raise DNSParseError(f"Unknown format: {format}")

    def parse_batch(self, lines: list[str], format: str = "auto") -> list[DNSEntry]:
        """Parse multiple DNS log lines, skipping malformed entries.

        Args:
            lines: List of log lines to parse.
            format: Format to use (same as parse_line).

        Returns:
            List of successfully parsed DNSEntry objects.
            Malformed lines are skipped and logged as warnings.
        """
        entries: list[DNSEntry] = []
        count = 0
        for line in lines:
            if count >= self._max_batch_size:
                logger.warning("Batch size limit reached, skipping remaining lines")
                break
            if not line or not line.strip():
                continue
            try:
                entry = self.parse_line(line, format=format)
                entries.append(entry)
                count += 1
            except DNSParseError:
                logger.debug("Skipping unparseable line", exc_info=True)
        return entries

    def _detect_format(self, line: str) -> str:
        if line.startswith("{"):
            return "json"
        if _SYSLOG_RE.search(line):
            return "syslog"
        if "." in line and _HOSTNAME_RE.match(line.strip()):
            return "raw"
        raise DNSParseError(f"Unable to auto-detect format for line: {line[:100]!r}")

    def _parse_syslog(self, line: str) -> DNSEntry:
        match = _SYSLOG_RE.search(line)
        if not match:
            raise DNSParseError(f"syslog format not matched: {line[:100]!r}")

        ts_str, source_ip, hostname, query_type = match.groups()
        timestamp = self._parse_syslog_timestamp(ts_str)
        return DNSEntry(
            hostname=hostname.lower(),
            source_ip=source_ip,
            timestamp=timestamp,
            query_type=query_type.upper(),
            raw=line,
        )

    def _parse_syslog_timestamp(self, ts_str: str) -> datetime:
        now = datetime.now(timezone.utc)
        try:
            parsed = datetime.strptime(ts_str, _SYSLOG_TIMESTAMP_FMT)
            return parsed.replace(year=now.year, tzinfo=timezone.utc)
        except ValueError:
            return now

    def _parse_json(self, line: str) -> DNSEntry:
        try:
            data: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as e:
            raise DNSParseError(f"Invalid JSON") from e

        hostname = data.get("query", "")
        source_ip = data.get("src_ip", "")
        timestamp = self._parse_json_timestamp(data.get("timestamp", ""))
        query_type = data.get("qtype", "A")
        response_ip = data.get("response_ip")

        if not hostname or not source_ip:
            raise DNSParseError("JSON missing required fields: query, src_ip")

        return DNSEntry(
            hostname=hostname.lower(),
            source_ip=source_ip,
            timestamp=timestamp,
            query_type=query_type.upper(),
            response_ip=response_ip,
            raw=line,
        )

    def _parse_json_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)

    def _parse_raw(self, line: str) -> DNSEntry:
        hostname = line.strip()
        if not hostname:
            raise DNSParseError("Empty raw format line")
        if not _HOSTNAME_RE.match(hostname) or "." not in hostname:
            raise DNSParseError(f"Invalid hostname: {hostname[:100]!r}")
        return DNSEntry(
            hostname=hostname.lower(),
            source_ip="0.0.0.0",
            timestamp=datetime.now(timezone.utc),
            query_type="A",
            raw=line,
        )
