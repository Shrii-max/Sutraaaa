"""Audit router: Append-only audit trail and integrity verification (Admin only)."""

from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import UserModel, AuditLogModel
from app.security.jwt import require_admin
from app.security.audit import AuditLogger
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])


class AuditLogEntryResponse(BaseModel):
    id: str
    timestamp: str
    event_type: str
    actor: str
    resource_id: Optional[str] = None
    input_payload: Optional[str] = None
    output_payload: Optional[str] = None
    confidence: Optional[float] = None
    needs_human_review: Optional[bool] = None
    status: str
    record_hash: str


class AuditTrailResponse(BaseModel):
    total_records: int
    hash_chain_status: str
    integrity_verified: bool
    records: List[AuditLogEntryResponse]
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.get("", response_model=AuditTrailResponse)
def get_audit_trail(
    limit: int = 100,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve append-only audit trail and verify cryptographic HMAC integrity (Admin only)."""
    stmt = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(limit)
    db_records = db.execute(stmt).scalars().all()

    # Verify HMAC chain
    is_valid = AuditLogger.verify_integrity()

    formatted = []
    for r in db_records:
        formatted.append(
            AuditLogEntryResponse(
                id=r.id,
                timestamp=r.timestamp.isoformat() if r.timestamp else "",
                event_type=r.event_type,
                actor=r.actor,
                resource_id=r.resource_id,
                input_payload=r.input_payload,
                output_payload=r.output_payload,
                confidence=r.confidence,
                needs_human_review=r.needs_human_review,
                status=r.status,
                record_hash=r.record_hash,
            )
        )

    # In case in-memory audit logs have recent events not yet flushed to DB
    if not formatted:
        mem_records = AuditLogger.get_records()
        for mr in mem_records[-limit:]:
            formatted.append(
                AuditLogEntryResponse(
                    id=getattr(mr, "id", getattr(mr, "record_id", "")),
                    timestamp=mr.timestamp,
                    event_type=mr.event_type,
                    actor=mr.actor,
                    resource_id=mr.resource_id,
                    input_payload=str(mr.input_payload) if mr.input_payload else None,
                    output_payload=str(mr.output_payload) if mr.output_payload else None,
                    confidence=mr.confidence,
                    needs_human_review=mr.needs_human_review,
                    status=mr.status,
                    record_hash=mr.record_hash,
                )
            )

    return AuditTrailResponse(
        total_records=len(formatted),
        hash_chain_status="INTACT" if is_valid else "TAMPERED_OR_CORRUPT",
        integrity_verified=is_valid,
        records=formatted,
        disclaimer=settings.DISCLAIMER_TEXT,
    )
