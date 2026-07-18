"""Local AES-256-GCM KMS backend for development and testing.

Per D-07, this implements the KMSClient ABC using AES-256-GCM
with HKDF key derivation. Suitable for dev/testing; production
should use AWS KMS or GCP KMS backends.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from anonreq.kms.base import KMSClient
from anonreq.kms.cache import InMemoryKeyCache


class LocalAES256GCM(KMSClient):
    """Local AES-256-GCM KMS backend.

    Per D-07, uses AES-256-GCM for authenticated encryption with
    HKDF-derived per-tenant data keys. The master key is used to
    derive unique data keys per tenant via HKDF.
    """

    def __init__(self, master_key: bytes, key_cache: InMemoryKeyCache) -> None:
        self._master_key = master_key
        self._cache = key_cache

    @staticmethod
    def generate_master_key() -> bytes:
        """Generate a fresh 256-bit master key."""
        return os.urandom(32)

    async def encrypt(self, tenant_id: str, plaintext: bytes) -> bytes:
        """Encrypt plaintext using tenant-specific AES-256-GCM key.

        Returns nonce + ciphertext_with_tag (12-byte nonce prepended).
        """
        data_key = await self._cache.get_or_derive(tenant_id, self._master_key)
        nonce = os.urandom(12)
        aesgcm = AESGCM(data_key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext_with_tag

    async def decrypt(self, tenant_id: str, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using tenant-specific AES-256-GCM key.

        Expects nonce (12 bytes) prepended to ciphertext_with_tag.
        Raises InvalidTag on tampering (AEAD verification).
        """
        if len(ciphertext) < 12:
            raise ValueError("ciphertext too short")

        nonce = ciphertext[:12]
        ciphertext_with_tag = ciphertext[12:]

        data_key = await self._cache.get_or_derive(tenant_id, self._master_key)
        aesgcm = AESGCM(data_key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
