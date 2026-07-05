"""eDiscovery export engine.

Provides compliance-grade export of lineage, DSAR, breach notification,
and retention data in JSONL, PDF, and EDRM XML formats.
"""

from __future__ import annotations

from anonreq.ediscovery.export import EDiscoveryExporter

__all__ = [
    "EDiscoveryExporter",
]
