"""KMS abstraction layer for tenant-scoped encryption.

Provides:
- ``KMSClient`` — abstract base class for pluggable KMS backends
- ``LocalAES256GCM`` — local AES-256-GCM implementation
- ``InMemoryKeyCache`` — bounded TTL cache for derived data keys

Per D-07, the KMS backend is configurable via ANONREQ_KMS_BACKEND.
Per D-08, ciphertext is stored in Valkey; plaintext never touches storage.
Per D-09, data keys are cached in-memory with bounded TTL.
"""

from anonreq.kms.base import KMSClient
from anonreq.kms.cache import InMemoryKeyCache
from anonreq.kms.local import LocalAES256GCM

__all__ = ["InMemoryKeyCache", "KMSClient", "LocalAES256GCM"]
