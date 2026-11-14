"""AES-256-GCM encryption at rest for legal documents and sensitive case files.

Follows Hard Rule 6: Documents are stored encrypted at rest (AES-256-GCM, key from env/KMS stub).
Includes tamper detection and KMS key provider abstraction.
"""

import os
import base64
from typing import Protocol, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from app.config import get_settings


class KMSKeyProvider(Protocol):
    """KMS interface stub for retrieving data encryption keys."""

    def get_data_key(self) -> bytes:
        """Retrieve 32-byte data encryption key for AES-256."""
        ...


class EnvKMSKeyProvider:
    """Default KMS stub provider that resolves the AES-256 key from environment/settings."""

    def __init__(self, key_str: Optional[str] = None):
        if not key_str:
            key_str = get_settings().DOCUMENT_ENCRYPTION_KEY
        
        # Accept hex string, base64 string, or raw 32-byte string
        try:
            if len(key_str) == 64:
                self._key = bytes.fromhex(key_str)
            else:
                self._key = base64.b64decode(key_str)
        except Exception:
            raw = key_str.encode("utf-8")
            if len(raw) < 32:
                # Pad to 32 bytes deterministically if short
                raw = raw.ljust(32, b"\0")
            self._key = raw[:32]

        if len(self._key) != 32:
            raise ValueError(f"AES-256 key must be exactly 32 bytes, got {len(self._key)}")

    def get_data_key(self) -> bytes:
        return self._key


_DEFAULT_KMS_PROVIDER = EnvKMSKeyProvider()


def get_default_kms_provider() -> KMSKeyProvider:
    return _DEFAULT_KMS_PROVIDER


def encrypt_bytes(
    data: bytes,
    key_provider: Optional[KMSKeyProvider] = None,
    associated_data: Optional[bytes] = None,
) -> bytes:
    """Encrypt plain bytes using AES-256-GCM.
    
    Structure of returned payload:
    [12 bytes Nonce] + [Ciphertext + 16 bytes Auth Tag]
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Data to encrypt must be bytes, got {type(data).__name__}")
    
    provider = key_provider or get_default_kms_provider()
    key = provider.get_data_key()
    
    # 96-bit (12-byte) nonce is cryptographically recommended for AES-GCM
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, data, associated_data)
    
    # Prepend nonce to ciphertext
    return nonce + ciphertext_and_tag


def decrypt_bytes(
    encrypted_payload: bytes,
    key_provider: Optional[KMSKeyProvider] = None,
    associated_data: Optional[bytes] = None,
) -> bytes:
    """Decrypt payload using AES-256-GCM and verify authenticity tag.
    
    Raises ValueError on corrupted or tampered payload.
    """
    if len(encrypted_payload) < 28:
        # 12 bytes nonce + 16 bytes tag minimum
        raise ValueError("Encrypted payload too short to be valid AES-GCM data")
    
    provider = key_provider or get_default_kms_provider()
    key = provider.get_data_key()
    
    nonce = encrypted_payload[:12]
    ciphertext_and_tag = encrypted_payload[12:]
    
    aesgcm = AESGCM(key)
    try:
        decrypted = aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)
        return decrypted
    except InvalidTag as err:
        raise ValueError("Decryption failed: Authentication tag mismatch (tampering detected)") from err

