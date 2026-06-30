"""Tokenization engine data models.

Per TOKN-01 through TOKN-07:
- Tokens follow the ``[TYPE_N]`` pattern with uppercase type (1-20 chars)
  and a positive integer N.
- TokenMapping records a single token-to-value association.
- TokenizationResult captures the full result of tokenizing a text.
- The TOKEN_PATTERN regex is a module-level constant for reuse by
  the restoration engine and response verification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TOKEN_PATTERN = re.compile(r"\[[A-Z][A-Z_]{0,19}_\d+\]")
"""Regex matching ``[TYPE_N]`` tokens per TOKN-01.

- ``[`` literal opening bracket
- ``[A-Z][A-Z_]{0,19}`` uppercase type (1-20 chars, may include underscore)
- ``_`` literal separator
- ``\d+`` one or more digits
- ``\]`` literal closing bracket

Reused by the restoration engine (SSE-04 case-insensitive matching) and
the post-restoration verification scan (METR-01).
"""


@dataclass
class TokenMapping:
    """A single token-to-original-value association.

    Attributes:
        token: The placeholder token (e.g. ``"[EMAIL_0]"``).
        original_value: The original sensitive value that was replaced.
    """

    token: str
    original_value: str


@dataclass
class TokenizationResult:
    """The full result of tokenizing a text.

    Attributes:
        tokenized_text: The text with all detected entities replaced by
            ``[TYPE_N]`` tokens.
        mappings: Dict mapping each token to its original value. Shared
            with CacheManager for Valkey storage.
    """

    tokenized_text: str
    mappings: dict[str, str] = field(default_factory=dict)
