"""Abstract base class for KMS backends.

Per D-07, the KMS backend defines async encrypt/decrypt methods
that operate on tenant-specific keys. Concrete implementations
include LocalAES256GCM (dev/testing) and future AWS/GCP KMS.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class KMSClient(ABC):
    """Abstract KMS backend for tenant-scoped encryption.

    Per D-07, this ABC defines the async encrypt/decrypt interface
    that all KMS backends must implement. The CacheManager uses this
    interface to transparently encrypt before Valkey write and
    decrypt after Valkey read per D-08.
    """

    @abstractmethod
    async def encrypt(self, tenant_id: str, plaintext: bytes) -> bytes:
        """Encrypt plaintext using tenant-specific key.

        Args:
            tenant_id: The tenant identifier for key selection.
            plaintext: The data to encrypt.

        Returns:
            Ciphertext bytes (includes nonce/tag prepended/appended).
        """

    @abstractmethod
    async def decrypt(self, tenant_id: str, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using tenant-specific key.

        Args:
            tenant_id: The tenant identifier for key selection.
            ciphertext: The encrypted data (includes nonce/tag).

        Returns:
            Decrypted plaintext bytes.

        Raises:
            Exception: On tampering (AEAD verification failure).
        """
