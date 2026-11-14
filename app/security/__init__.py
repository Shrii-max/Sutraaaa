"""Security module for LexAgent."""
from app.security.encryption import encrypt_bytes, decrypt_bytes, KMSKeyProvider
from app.security.crypto import encrypt_file, decrypt_file, EncryptedFileStore, parse_encryption_key
from app.security.audit import AuditLogger, record_audit_event

__all__ = [
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_file",
    "decrypt_file",
    "EncryptedFileStore",
    "parse_encryption_key",
    "KMSKeyProvider",
    "AuditLogger",
    "record_audit_event",
]
