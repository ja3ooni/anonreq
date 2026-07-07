"""ResponseScanner — post-restoration token detection for residual ``[TYPE_N]`` patterns.

Per D-143 through D-146:
- Scans completed response content for remaining ``[TYPE_N]`` tokens
- Stateless and pure — takes string input, returns structured ``ScanResult``
- Used by ``ScanStage`` (non-streaming) and ``StreamScanStage`` (streaming)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Matches [TYPE_N] where TYPE is 1-20 uppercase chars/underscores, N is positive integer
TOKEN_PATTERN = re.compile(r"\[[A-Z][A-Z_]{0,49}_\d+\]")


@dataclass
class ScanResult:
    """Result of scanning a text for residual tokens.

    Attributes:
        match_count: Number of token matches found.
        matches: List of matched token strings (e.g. ``["[NAME_1]", "[EMAIL_0]"]``).
        positions: List of ``(start, end)`` character offsets for each match.
    """

    match_count: int = 0
    matches: list[str] = field(default_factory=list)
    positions: list[tuple[int, int]] = field(default_factory=list)


class ResponseScanner:
    """Scans text for residual ``[TYPE_N]`` token patterns.

    Usage::

        scanner = ResponseScanner()
        result = scanner.scan("Hello [NAME_1]")
        # ScanResult(match_count=1, matches=["[NAME_1]"], positions=[(6, 14)])
    """

    def scan(self, text: str) -> ScanResult:
        """Scan the given text for residual token patterns.

        Args:
            text: The text to scan, typically a response body or assembled
                stream content.

        Returns:
            A ``ScanResult`` with match count, matched strings, and positions.
            Returns ``ScanResult(match_count=0)`` if no tokens are found.
        """
        if not text:
            return ScanResult(match_count=0)

        matches = list(TOKEN_PATTERN.finditer(text))
        if not matches:
            return ScanResult(match_count=0)

        return ScanResult(
            match_count=len(matches),
            matches=[m.group() for m in matches],
            positions=[(m.start(), m.end()) for m in matches],
        )
