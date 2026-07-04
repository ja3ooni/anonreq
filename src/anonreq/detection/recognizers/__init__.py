"""MNPI (Material Non-Public Information) recognizer bundle.

Provides Presidio-compatible recognizers for:
- Ticker symbols (NYSE/NASDAQ 1-4 uppercase letters, optional dot suffix)
- Deal codenames (Project/Operation/Initiative patterns)
- Tenant restricted-names list entries

Per D-001, D-002, D-003: dedicated recognizer bundle for MNPI detection
with 4 policy actions: anonymize_and_forward, flag_and_forward, block, quarantine.
"""

from anonreq.detection.recognizers.mnpi import MNPIConfig, MNPIRecognizer, create_mnpi_bundle

__all__ = [
    "MNPIConfig",
    "MNPIRecognizer",
    "create_mnpi_bundle",
]
