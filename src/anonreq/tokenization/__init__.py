"""Tokenization engine — replaces PII spans with ``[TYPE_N]`` placeholders.

Per TOKN-01 through TOKN-07 the tokenizer:
- Generates ``[TYPE_N]`` tokens with uppercase type (1-20 chars) and positive N
- Deduplicates identical entity values within a session
- Uses reverse-offset replacement to prevent position drift
- Derives token indices from a cryptographically random seed per session
- Returns original text unchanged when no entities are detected

Also exports ``Restorer`` for token-to-value replacement in responses.
"""

from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import TOKEN_PATTERN, Tokenizer

__all__ = [
    "TOKEN_PATTERN",
    "Restorer",
    "Tokenizer",
]
