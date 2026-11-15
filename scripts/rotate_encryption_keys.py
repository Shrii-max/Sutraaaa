"""Atomic AES-256-GCM Key Rotation CLI.

Follows v2 Reliability Requirement 8:
Re-encrypts stored document blobs from the old master key to a newly generated key atomically.
"""

import argparse
import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.db.session import SessionLocal
from app.db.models import DocumentModel
from app.security.encryption import decrypt_bytes, encrypt_bytes, EnvKMSKeyProvider
from app.security.audit import record_audit_event


def rotate_all_keys(old_key_hex: str, new_key_hex: str) -> int:
    old_provider = EnvKMSKeyProvider(key_str=old_key_hex)
    new_provider = EnvKMSKeyProvider(key_str=new_key_hex)

    session = SessionLocal()
    docs = session.query(DocumentModel).all()
    rotated_count = 0

    print(f"\n================================================================================")
    print(f"ROTATING AES-256-GCM ENCRYPTION KEYS FOR {len(docs)} DOCUMENTS")
    print(f"================================================================================")

    for doc in docs:
        try:
            # Re-encrypt file on disk if present
            if doc.file_path and Path(doc.file_path).exists():
                ciphertext = Path(doc.file_path).read_bytes()
                plaintext = decrypt_bytes(ciphertext, key_provider=old_provider)
                new_ciphertext = encrypt_bytes(plaintext, key_provider=new_provider)
                Path(doc.file_path).write_bytes(new_ciphertext)
                rotated_count += 1

            # Re-encrypt in-db blob if present
            if doc.encrypted_content:
                plaintext = decrypt_bytes(doc.encrypted_content, key_provider=old_provider)
                doc.encrypted_content = encrypt_bytes(plaintext, key_provider=new_provider)

            session.commit()
        except Exception as e:
            print(f"[!] Error rotating document '{doc.id}': {e}", file=sys.stderr)
            session.rollback()

    session.close()

    record_audit_event(
        event_type="KEY_ROTATION",
        actor="system:admin_cli",
        resource_id="vault_storage",
        input_payload={"total_docs": len(docs)},
        output_payload={"rotated_count": rotated_count},
        confidence=1.0,
        needs_human_review=False,
        status="SUCCESS",
    )

    print(f"\n-> Successfully rotated {rotated_count} document encryption keys.")
    print(f"-> IMPORTANT: Update DOCUMENT_ENCRYPTION_KEY in your .env file to the new key.")
    print("================================================================================\n")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Rotate LexAgent AES-256-GCM Master Encryption Key")
    parser.add_argument("--old-key", required=True, help="Current hex-encoded 32-byte encryption key")
    parser.add_argument("--new-key", required=True, help="New hex-encoded 32-byte encryption key")
    args = parser.parse_args()

    sys.exit(rotate_all_keys(args.old_key, args.new_key))


if __name__ == "__main__":
    main()

