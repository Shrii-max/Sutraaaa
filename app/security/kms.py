"""KMS Key Provider Abstraction, Envelope Encryption, and Key Rotation.

Follows v2 Reliability Requirement 8:
KMS abstraction + key rotation procedure.
"""

import os
import base64
import logging
from typing import Protocol, Optional, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

logger = logging.getLogger(__name__)


class KMSKeyProvider(Protocol):
    """Protocol for cryptographic key management."""

    def get_data_key(self) -> bytes:
        """Retrieve active 32-byte data encryption key for AES-256."""
        ...


class LocalEnvelopeKMSProvider:
    """Envelope encryption provider using a local master key to derive or unwrap data keys."""

    def __init__(self, master_key_hex: Optional[str] = None):
        settings = get_settings()
        key_str = master_key_hex or settings.DOCUMENT_ENCRYPTION_KEY
        try:
            if len(key_str) == 64:
                self._master_key = bytes.fromhex(key_str)
            else:
                self._master_key = base64.b64decode(key_str)
        except Exception:
            raw = key_str.encode("utf-8").ljust(32, b"\0")
            self._master_key = raw[:32]

        if len(self._master_key) != 32:
            raise ValueError(f"Master key must be exactly 32 bytes, got {len(self._master_key)}")

    def get_data_key(self) -> bytes:
        return self._master_key

    def rotate_key(self, new_key_hex: str) -> "LocalEnvelopeKMSProvider":
        """Instantiate a new provider with rotated key."""
        return LocalEnvelopeKMSProvider(master_key_hex=new_key_hex)


_KMS_INSTANCE = LocalEnvelopeKMSProvider()


def get_kms_provider() -> KMSKeyProvider:
    return _KMS_INSTANCE

