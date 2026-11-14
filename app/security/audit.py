"""Append-only audit log system with HMAC integrity protection.

Follows Hard Rule 5: Every agent run and every API access writes an append-only audit log row.
"""

import hmac
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.config import get_settings
from app.security.guardrails import mask_pii


class AuditRecord(BaseModel):
    """Schema for append-only audit records."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event_type: str  # "API_ACCESS", "AGENT_RUN", "DOCUMENT_INGEST", "PRECEDENT_QUERY"
    actor: str       # e.g., "advocate_user", "system_orchestrator", "agent_name"
    resource_id: Optional[str] = None
    input_payload: Optional[str] = None
    output_payload: Optional[str] = None
    confidence: Optional[float] = None
    needs_human_review: Optional[bool] = None
    status: str = "SUCCESS"  # SUCCESS, FAILURE, ERROR
    prev_hash: str = "GENESIS"
    record_hash: str = ""


class AuditLogger:
    """Manages append-only audit logging with cryptographic chaining."""

    _last_hash: str = "0" * 64
    _memory_log: list[AuditRecord] = []

    def __init__(self, secret: Optional[str] = None):
        self.secret = (secret or get_settings().AUDIT_HMAC_SECRET).encode("utf-8")

    def _compute_hash(self, record_dict: Dict[str, Any], prev_hash: str) -> str:
        """Compute HMAC SHA-256 over record contents and previous hash."""
        serialized = json.dumps(record_dict, sort_keys=True, default=str)
        payload = f"{prev_hash}|{serialized}".encode("utf-8")
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def log(
        self,
        event_type: str,
        actor: str,
        resource_id: Optional[str] = None,
        input_payload: Optional[Any] = None,
        output_payload: Optional[Any] = None,
        confidence: Optional[float] = None,
        needs_human_review: Optional[bool] = None,
        status: str = "SUCCESS",
    ) -> AuditRecord:
        """Create and store an append-only audit entry."""
        # Sanitize payloads to string representations
        str_in = (
            json.dumps(input_payload, default=str)
            if input_payload is not None and not isinstance(input_payload, str)
            else input_payload
        )
        str_out = (
            json.dumps(output_payload, default=str)
            if output_payload is not None and not isinstance(output_payload, str)
            else output_payload
        )

        # Enforce PII masking in audit trail (Phase 6)
        if str_in:
            str_in = mask_pii(str_in)
        if str_out:
            str_out = mask_pii(str_out)

        record_data = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "resource_id": resource_id,
            "input_payload": str_in,
            "output_payload": str_out,
            "confidence": confidence,
            "needs_human_review": needs_human_review,
            "status": status,
            "prev_hash": AuditLogger._last_hash,
        }

        # Calculate cryptographically verifiable hash
        calc_hash = self._compute_hash(record_data, AuditLogger._last_hash)
        record_data["record_hash"] = calc_hash

        record = AuditRecord(**record_data)
        AuditLogger._last_hash = calc_hash
        AuditLogger._memory_log.append(record)

        return record

    @classmethod
    def get_records(cls) -> list[AuditRecord]:
        """Return audit trail for review or compliance inspection."""
        return list(cls._memory_log)

    @classmethod
    def reset(cls) -> None:
        """Reset in-memory log for test isolation."""
        cls._last_hash = "0" * 64
        cls._memory_log = []

    @classmethod
    def verify_integrity(cls, secret: Optional[str] = None) -> bool:
        """Verify the cryptographic hash chain of the entire audit trail."""
        sec = (secret or get_settings().AUDIT_HMAC_SECRET).encode("utf-8")
        expected_prev = "0" * 64

        for rec in cls._memory_log:
            rec_dict = rec.model_dump(exclude={"record_hash"})
            serialized = json.dumps(rec_dict, sort_keys=True, default=str)
            payload = f"{expected_prev}|{serialized}".encode("utf-8")
            expected_hash = hmac.new(sec, payload, hashlib.sha256).hexdigest()
            if rec.record_hash != expected_hash:
                return False
            expected_prev = rec.record_hash
        return True


_GLOBAL_AUDIT_LOGGER = AuditLogger()


def record_audit_event(
    event_type: str,
    actor: str,
    resource_id: Optional[str] = None,
    input_payload: Optional[Any] = None,
    output_payload: Optional[Any] = None,
    confidence: Optional[float] = None,
    needs_human_review: Optional[bool] = None,
    status: str = "SUCCESS",
) -> AuditRecord:
    """Helper to record audit event using the global logger."""
    return _GLOBAL_AUDIT_LOGGER.log(
        event_type=event_type,
        actor=actor,
        resource_id=resource_id,
        input_payload=input_payload,
        output_payload=output_payload,
        confidence=confidence,
        needs_human_review=needs_human_review,
        status=status,
    )
