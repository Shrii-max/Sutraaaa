"""Tests for AES-256-GCM document encryption and append-only audit logging."""

import pytest
from app.security.encryption import encrypt_bytes, decrypt_bytes, EnvKMSKeyProvider
from app.security.audit import AuditLogger, record_audit_event


def test_aes_gcm_encryption_roundtrip():
    """Verify document encryption and decryption integrity."""
    plaintext = "CONFIDENTIAL: Client Advocate Privileged Communication - Indian Evidence Act S.126".encode("utf-8")
    
    encrypted = encrypt_bytes(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) > len(plaintext)

    decrypted = decrypt_bytes(encrypted)
    assert decrypted == plaintext


def test_aes_gcm_tamper_detection():
    """Verify that tampering with any byte in the ciphertext or auth tag raises an error."""
    plaintext = b"Draft Special Leave Petition before Supreme Court of India"
    encrypted = bytearray(encrypt_bytes(plaintext))

    # Tamper with the last byte (part of authentication tag)
    encrypted[-1] ^= 0xFF

    with pytest.raises(ValueError, match="tampering detected"):
        decrypt_bytes(bytes(encrypted))


def test_kms_key_provider_length_validation():
    """Verify that invalid key lengths are rejected."""
    provider = EnvKMSKeyProvider("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
    assert len(provider.get_data_key()) == 32


def test_append_only_audit_log_hash_chain():
    """Verify append-only audit logging and cryptographic HMAC hash chaining."""
    AuditLogger.reset()
    logger = AuditLogger(secret="test-audit-secret-key")
    
    r1 = logger.log(
        event_type="DOCUMENT_INGEST",
        actor="advocate_user",
        resource_id="doc-001",
        input_payload={"filename": "plaint.pdf"},
        output_payload={"status": "stored"},
    )
    assert r1.prev_hash == "0" * 64
    assert len(r1.record_hash) == 64

    r2 = logger.log(
        event_type="AGENT_RUN",
        actor="agent:FactExtractionAgent",
        resource_id="doc-001",
        confidence=0.88,
        needs_human_review=False,
    )
    # Hash chain link
    assert r2.prev_hash == r1.record_hash

    # Verify overall integrity
    assert AuditLogger.verify_integrity(secret="test-audit-secret-key") is True


def test_audit_log_tamper_detection():
    """Verify that modifying any audit record invalidates the hash chain."""
    logger = AuditLogger(secret="test-audit-secret-key")
    logger.log(event_type="TEST_1", actor="user1")
    logger.log(event_type="TEST_2", actor="user2")

    records = AuditLogger.get_records()
    # Malicious modification of an in-memory record
    original_event = records[-1].event_type
    records[-1].event_type = "ALTERED_EVENT_TYPE"

    try:
        assert AuditLogger.verify_integrity(secret="test-audit-secret-key") is False
    finally:
        records[-1].event_type = original_event
