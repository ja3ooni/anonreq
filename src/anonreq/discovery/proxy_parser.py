"""Proxy access log parser supporting Squid, Zscaler, and Palo Alto formats.

Per D-001, D-003:
- Squid format: timestamp, elapsed, client, status, size, method, url, user, hierarchy, type
- Zscaler format: CSV with device, datetime, user, department, url, action, reason, status, bytes, content_type
- Palo Alto format: timestamp, serial, type, subtype, src_ip, dest_ip, dest_port, url, user, action, bytes
- Invalid lines return None (skip, no error)
- Parser is read-only: no mutations from parsed content
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SQUID_RE = re.compile(
    r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)"
)
_ZSCALER_FIELDS = [
    "device", "datetime", "user", "department", "url",
    "action", "reason", "status", "bytes", "content_type",
]
_PALO_ALTO_RE = re.compile(
    r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}),"
    r"([^,]+),([^,]+),([^,]+),"
    r"([^,]+),([^,]+),(\d+),"
    r"([^,]+),([^,]*),([^,]+),(\d+)"
)


class ProxyEntry:
    """Represents a parsed proxy log entry.

    Attributes:
        source_ip: IP address of the client.
        timestamp: When the request occurred.
        method: HTTP method (GET, POST, etc.).
        url: The requested URL.
        status: HTTP status code.
        bytes: Number of bytes transferred.
        user_id: Authenticated user identifier, if available.
        content_type: Response content type, if available.
        user_agent: User agent string, if available.
    """

    __slots__ = (
        "source_ip", "timestamp", "method", "url", "status",
        "bytes", "user_id", "content_type", "user_agent",
    )

    def __init__(
        self,
        source_ip: str,
        timestamp: datetime,
        method: str,
        url: str,
        status: int,
        bytes: int,
        user_id: str | None = None,
        content_type: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.source_ip = source_ip
        self.timestamp = timestamp
        self.method = method
        self.url = url
        self.status = status
        self.bytes = bytes
        self.user_id = user_id
        self.content_type = content_type
        self.user_agent = user_agent

    def __repr__(self) -> str:
        return (
            f"ProxyEntry(source_ip={self.source_ip!r}, method={self.method!r}, "
            f"url={self.url!r}, status={self.status})"
        )


class ProxyParser:
    """Parses proxy access log lines from multiple formats.

    Args:
        max_batch_size: Maximum number of lines to parse in a single batch.
            Defaults to 10,000.
    """

    def __init__(self, max_batch_size: int = 10_000) -> None:
        self._max_batch_size = max_batch_size

    def parse_line(self, line: str, format: str = "auto") -> ProxyEntry | None:
        """Parse a single proxy log line.

        Args:
            line: The log line to parse.
            format: One of "auto", "squid", "zscaler", or "paloalto".

        Returns:
            ProxyEntry if parsed successfully, None if the line cannot be parsed.
        """
        if not line or not line.strip():
            return None

        stripped = line.strip()

        if format == "auto":
            format = self._detect_format(stripped)

        if format == "squid":
            return self._parse_squid(stripped)
        elif format == "zscaler":
            return self._parse_zscaler(stripped)
        elif format == "paloalto":
            return self._parse_palo_alto(stripped)
        else:
            return None

    def parse_batch(self, lines: list[str], format: str = "auto") -> list[ProxyEntry]:
        """Parse multiple proxy log lines, skipping invalid entries.

        Args:
            lines: List of log lines to parse.
            format: Format to use (same as parse_line).

        Returns:
            List of successfully parsed ProxyEntry objects.
        """
        entries: list[ProxyEntry] = []
        count = 0
        for line in lines:
            if count >= self._max_batch_size:
                break
            if not line or not line.strip():
                continue
            entry = self.parse_line(line, format=format)
            if entry is not None:
                entries.append(entry)
                count += 1
        return entries

    def _detect_format(self, line: str) -> str:
        if line[0].isdigit() and "." in line[:20]:
            return "squid"
        if line.startswith("20") and "/" in line[:11]:
            return "paloalto"
        if "," in line and len(line.split(",")) >= 6:
            return "zscaler"
        return "squid"

    def _parse_squid(self, line: str) -> ProxyEntry | None:
        match = _SQUID_RE.match(line)
        if not match:
            return None

        timestamp_str = match.group(1)
        status_code_str = match.group(5)
        size_str = match.group(6)
        method = match.group(7)
        url = match.group(8)
        user = match.group(9)
        content_type = match.group(11)

        try:
            timestamp = datetime.fromtimestamp(float(timestamp_str), tz=timezone.utc)
        except (ValueError, OSError):
            timestamp = datetime.now(timezone.utc)

        try:
            status = int(status_code_str)
        except (ValueError, TypeError):
            status = 0

        try:
            size = int(size_str)
        except (ValueError, TypeError):
            size = 0

        user_id = user if user and user != "-" else None

        return ProxyEntry(
            source_ip=match.group(3),
            timestamp=timestamp,
            method=method.upper(),
            url=url,
            status=status,
            bytes=size,
            user_id=user_id,
            content_type=content_type if content_type and content_type != "-" else None,
        )

    def _parse_zscaler(self, line: str) -> ProxyEntry | None:
        parts = line.split(",")
        if len(parts) < 8:
            return None

        device = parts[0].strip()
        ts_str = parts[1].strip()
        user = parts[2].strip()
        url = parts[4].strip()
        status_str = parts[7].strip()
        bytes_str = parts[8].strip() if len(parts) > 8 else "0"
        content_type = parts[9].strip() if len(parts) > 9 else ""

        timestamp = self._parse_zscaler_timestamp(ts_str)

        try:
            status = int(status_str)
        except (ValueError, TypeError):
            status = 0

        try:
            size = int(bytes_str)
        except (ValueError, TypeError):
            size = 0

        method = "GET" if "rest." not in url and "v1/" not in url else "POST"

        return ProxyEntry(
            source_ip=device,
            timestamp=timestamp,
            method=method,
            url=url,
            status=status,
            bytes=size,
            user_id=user if user else None,
            content_type=content_type if content_type else None,
        )

    def _parse_zscaler_timestamp(self, ts_str: str) -> datetime:
        try:
            return datetime.strptime(ts_str, "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)

    def _parse_palo_alto(self, line: str) -> ProxyEntry | None:
        match = _PALO_ALTO_RE.match(line)
        if not match:
            return None

        ts_str = match.group(1)
        src_ip = match.group(5)
        url = match.group(8)
        user = match.group(9)
        action = match.group(10)
        bytes_str = match.group(11)

        try:
            timestamp = datetime.strptime(ts_str, "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        try:
            size = int(bytes_str)
        except (ValueError, TypeError):
            size = 0

        status = 200 if action.upper() == "ALLOW" else 403
        method = "POST" if "v1/" in url else "GET"

        return ProxyEntry(
            source_ip=src_ip,
            timestamp=timestamp,
            method=method,
            url=url,
            status=status,
            bytes=size,
            user_id=user if user else None,
        )
