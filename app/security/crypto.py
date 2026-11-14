"""AES-256-GCM authenticated encryption for files and encrypted storage helper.

Follows Hard Rule 6: Documents are stored encrypted at rest (AES-256-GCM, key from env/KMS stub).
Includes file encryption/decryption and encrypted disk vault storage helper.
"""

import os
import base64
import hashlib
import uuid
from pathlib import Path
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from app.config import get_settings


def parse_encryption_key(key_str: Optional[str] = None) -> bytes:
    """Parse a 32-byte AES key from hex, base64, or raw string representation."""
    if not key_str:
        key_str = get_settings().ENCRYPTION_KEY

    try:
        if len(key_str) == 64:
            key_bytes = bytes.fromhex(key_str)
        else:
            key_bytes = base64.b64decode(key_str)
    except Exception:
        raw = key_str.encode("utf-8")
        if len(raw) < 32:
            raw = raw.ljust(32, b"\0")
        key_bytes = raw[:32]

    if len(key_bytes) != 32:
        raise ValueError(f"AES-256 key must be exactly 32 bytes, got {len(key_bytes)}")
    return key_bytes


def encrypt_file(
    file_bytes: bytes,
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None,
) -> bytes:
    """Encrypt raw file bytes using AES-256-GCM.
    
    Structure:
    [12-byte Nonce] + [Ciphertext + 16-byte GCM Authentication Tag]
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise TypeError(f"Data to encrypt must be bytes, got {type(file_bytes).__name__}")

    raw_key = key if key is not None else parse_encryption_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(raw_key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, file_bytes, associated_data)
    return nonce + ciphertext_and_tag


def decrypt_file(
    encrypted_bytes: bytes,
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None,
) -> bytes:
    """Decrypt AES-256-GCM encrypted payload and authenticate integrity.
    
    Raises ValueError on tampering or tag mismatch.
    """
    if len(encrypted_bytes) < 28:
        raise ValueError("Encrypted payload too short (minimum 12 bytes nonce + 16 bytes tag)")

    raw_key = key if key is not None else parse_encryption_key()
    nonce = encrypted_bytes[:12]
    ciphertext_and_tag = encrypted_bytes[12:]

    aesgcm = AESGCM(raw_key)
    try:
        return aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)
    except InvalidTag as err:
        raise ValueError("Decryption failed: Authentication tag mismatch (tampering detected)") from err


decrypt_bytes = decrypt_file
encrypt_bytes = encrypt_file


class EncryptedFileStore:
    """Helper to store and retrieve encrypted document blobs on the filesystem."""

    def __init__(self, storage_dir: Optional[str] = None):
        settings = get_settings()
        self.base_dir = Path(storage_dir or settings.ENCRYPTED_STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        file_bytes: bytes,
        original_filename: str,
        case_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Encrypts bytes and saves them to vault.
        
        Returns:
            Tuple[str, str]: (relative_file_path, sha256_hash)
        """
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        encrypted = encrypt_file(file_bytes)

        file_id = f"{uuid.uuid4().hex}.enc"
        if case_id:
            sub_dir = self.base_dir / case_id
            sub_dir.mkdir(parents=True, exist_ok=True)
            target_path = sub_dir / file_id
            rel_path = f"{case_id}/{file_id}"
        else:
            target_path = self.base_dir / file_id
            rel_path = file_id

        target_path.write_bytes(encrypted)
        return rel_path, sha256_hash

    def retrieve(self, relative_path: str) -> bytes:
        """Read encrypted blob from vault and decrypt back to plaintext bytes."""
        full_path = (self.base_dir / relative_path).resolve()
        if not full_path.exists():
            raise FileNotFoundError(f"Encrypted file not found at: {full_path}")
        encrypted_bytes = full_path.read_bytes()
        return decrypt_file(encrypted_bytes)

    def delete(self, relative_path: str) -> bool:
        """Securely remove encrypted blob from vault."""
        full_path = (self.base_dir / relative_path).resolve()
        if full_path.exists():
            full_path.unlink()
            return True
        return False

