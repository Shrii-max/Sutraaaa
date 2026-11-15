"""Cases router: Case file management, document uploads, and case-level intelligence views.

Enforces tenant isolation: lawyers can only access their own cases (admins can access all).
All business logic is delegated to CaseManager and DocumentManager.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.db.session import get_db
from app.db.models import (
    UserModel,
    DocumentTranslationModel,
    VoiceBriefModel,
    FactModel,
    SummaryModel,
    TimelineEventModel,
    ContradictionModel,
    ValidationIssueModel,
)
from app.security.jwt import get_current_user, require_lawyer
from app.services.case_manager import CaseManager
from app.services.document_manager import DocumentManager
from app.schemas.translation import TranslatedSummary
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/cases", tags=["Cases & Intelligence"])


# -----------------------------------------------------------------------------
# Request & Response Schemas with Clean OpenAPI Examples
# -----------------------------------------------------------------------------
class CreateCaseRequest(BaseModel):
    title: str = Field(
        ...,
        description="Matter title (e.g. Parties name or description)",
        json_schema_extra={"example": "State of Maharashtra v. Devendra Patil & Ors."},
    )
    case_number: Optional[str] = Field(
        None,
        description="Court formal case registration number",
        json_schema_extra={"example": "Sessions Case No. 412/2023"},
    )
    court: Optional[str] = Field(
        None,
        description="Court or forum of jurisdiction",
        json_schema_extra={"example": "Sessions Court at Greater Bombay"},
    )
    dpdp_purpose: Optional[str] = Field(
        default="Legal Defense & Case Preparation",
        description="Purpose of data processing under DPDP Act",
        json_schema_extra={"example": "Criminal Trial Defense & Legal Advice"},
    )
    retention_days: Optional[int] = Field(
        default=365,
        description="Data retention period in days before scheduled crypto-shredding",
        json_schema_extra={"example": 365},
    )


class CaseResponse(BaseModel):
    id: str = Field(..., description="Unique case identifier", json_schema_extra={"example": "case-94a2b1"})
    title: str = Field(..., json_schema_extra={"example": "State of Maharashtra v. Devendra Patil & Ors."})
    case_number: Optional[str] = Field(None, json_schema_extra={"example": "Sessions Case No. 412/2023"})
    court: Optional[str] = Field(None, json_schema_extra={"example": "Sessions Court at Greater Bombay"})
    status: str = Field("open", json_schema_extra={"example": "open"})
    created_at: str
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


class CaseListResponse(BaseModel):
    total_cases: int = Field(..., json_schema_extra={"example": 1})
    cases: List[CaseResponse]
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


class DocumentUploadStatusResponse(BaseModel):
    document_id: str = Field(..., json_schema_extra={"example": "doc-8321a"})
    case_id: str = Field(..., json_schema_extra={"example": "case-94a2b1"})
    filename: str = Field(..., json_schema_extra={"example": "FIR_2023_04.pdf"})
    sha256_hash: str
    status: str = Field("pending", description="Initial status: pending/running", json_schema_extra={"example": "pending"})
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    req: CreateCaseRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Create a new case file owned by the authenticated lawyer."""
    manager = CaseManager(db)
    case = manager.create_case(
        user_id=current_user.id,
        title=req.title,
        case_number=req.case_number,
        court=req.court,
        dpdp_purpose=req.dpdp_purpose,
        retention_days=req.retention_days,
    )
    return CaseResponse(
        id=case.id,
        title=case.title,
        case_number=case.case_number,
        court=case.court,
        status=case.status,
        created_at=case.created_at.isoformat() if case.created_at else "",
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.get("", response_model=CaseListResponse)
def list_cases(
    limit: int = 50,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """List legal cases owned by the authenticated lawyer (enforces tenant isolation)."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    cases = manager.list_cases(user_id=current_user.id, is_admin=is_admin, limit=limit)
    return CaseListResponse(
        total_cases=len(cases),
        cases=[
            CaseResponse(
                id=c.id,
                title=c.title,
                case_number=c.case_number,
                court=c.court,
                status=c.status,
                created_at=c.created_at.isoformat() if c.created_at else "",
                disclaimer=settings.DISCLAIMER_TEXT,
            )
            for c in cases
        ],
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.get("/{id}", response_model=CaseResponse)
def get_case(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get case details by ID. Rejects cross-lawyer access with 403 Forbidden."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    case = manager.get_case(case_id=id, user_id=current_user.id, is_admin=is_admin)
    return CaseResponse(
        id=case.id,
        title=case.title,
        case_number=case.case_number,
        court=case.court,
        status=case.status,
        created_at=case.created_at.isoformat() if case.created_at else "",
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.post("/{id}/documents", response_model=DocumentUploadStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_case_document(
    id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Upload document to case: encrypts with AES-256-GCM and starts multi-agent processing."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    content = await file.read()
    doc = manager.upload_document(
        case_id=id,
        user_id=current_user.id,
        filename=file.filename or "document.pdf",
        content=content,
        background_tasks=background_tasks,
        is_admin=is_admin,
    )
    return DocumentUploadStatusResponse(
        document_id=doc.id,
        case_id=id,
        filename=doc.filename,
        sha256_hash=doc.sha256_hash,
        status=doc.status,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.get("/{id}/timeline")
def get_case_timeline(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Retrieve chronological timeline of incidents, FIR, arrests, and hearings for case."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_timeline(case_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/statements")
def get_case_statements(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Retrieve index of victim and witness statements (Section 161/164 CrPC / BNSS) across all case documents."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_statements(case_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/contradictions")
def get_case_contradictions(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Retrieve cross-document contradictions between witnesses, depositions, and FIR."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_contradictions(case_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/similar-cases")
def get_case_similar_cases(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Retrieve database-verified precedent cases (Hard Rule 4: zero hallucination)."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_similar_cases(case_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/dashboard")
def get_case_dashboard(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Comprehensive case intelligence overview: document statuses, defects, and risk flags."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_dashboard(case_id=id, user_id=current_user.id, is_admin=is_admin)


# -----------------------------------------------------------------------------
# DPDP Compliance: Case Erasure & Cryptographic Shredding
# -----------------------------------------------------------------------------
import os
from pathlib import Path
from datetime import datetime, timezone
from app.db.models import CaseModel, DocumentModel
from app.security.audit import record_audit_event


class CryptoShredRequest(BaseModel):
    confirmation: str = Field(
        ...,
        description="Must be 'PERMANENTLY_SHRED_CASE_DATA' to confirm permanent deletion",
        json_schema_extra={"example": "PERMANENTLY_SHRED_CASE_DATA"},
    )
    reason: Optional[str] = Field(
        default="Client requested erasure under DPDP",
        description="Reason for cryptographic shredding and erasure",
    )


class CryptoShredResponse(BaseModel):
    case_id: str
    status: str = "CRYPTO_SHREDDED"
    shredded_at: str
    files_destroyed_count: int
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.post("/{id}/shred", response_model=CryptoShredResponse)
def crypto_shred_case(
    id: str,
    payload: CryptoShredRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Permanently crypto-shreds all case documents, wipes blobs, and logs immutable audit trail."""
    from fastapi import HTTPException
    if payload.confirmation != "PERMANENTLY_SHRED_CASE_DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase must match 'PERMANENTLY_SHRED_CASE_DATA' exactly.",
        )

    case = db.scalar(select(CaseModel).where(CaseModel.id == id))
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{id}' not found.")

    if current_user.role != "admin" and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    destroyed_count = 0
    now = datetime.now(timezone.utc)

    # Overwrite and remove document files
    for doc in case.documents:
        if doc.file_path and Path(doc.file_path).exists():
            try:
                # Overwrite ciphertext with zeroes before unlinking (shredding)
                f_path = Path(doc.file_path)
                size = f_path.stat().st_size
                f_path.write_bytes(os.urandom(size))
                f_path.unlink()
                destroyed_count += 1
            except Exception:
                pass
        doc.encrypted_content = None
        doc.status = "shredded"

    # Crypto-shred voice audio files on disk and records
    voice_briefs = list(db.scalars(select(VoiceBriefModel).where(VoiceBriefModel.case_id == id)))
    for vb in voice_briefs:
        if vb.audio_path and Path(vb.audio_path).exists():
            try:
                p = Path(vb.audio_path)
                p.write_bytes(os.urandom(p.stat().st_size))
                p.unlink()
                destroyed_count += 1
            except Exception:
                pass

    db.execute(delete(VoiceBriefModel).where(VoiceBriefModel.case_id == id))
    db.execute(delete(DocumentTranslationModel).where(DocumentTranslationModel.case_id == id))
    db.execute(delete(FactModel).where(FactModel.case_id == id))
    db.execute(delete(SummaryModel).where(SummaryModel.case_id == id))
    db.execute(delete(TimelineEventModel).where(TimelineEventModel.case_id == id))
    db.execute(delete(ContradictionModel).where(ContradictionModel.case_id == id))
    db.execute(delete(ValidationIssueModel).where(ValidationIssueModel.document_id.in_([d.id for d in case.documents])))

    case.is_crypto_shredded = True
    case.shredded_at = now
    case.status = "closed_shredded"
    db.commit()

    record_audit_event(
        event_type="DPDP_CASE_CRYPTO_SHRED",
        actor=f"user:{current_user.email}",
        resource_id=id,
        input_payload={"reason": payload.reason},
        output_payload={"status": "CRYPTO_SHREDDED", "files_destroyed": destroyed_count},
        confidence=1.0,
        needs_human_review=False,
        status="SUCCESS",
    )

    return CryptoShredResponse(
        case_id=case.id,
        status="CRYPTO_SHREDDED",
        shredded_at=now.isoformat(),
        files_destroyed_count=destroyed_count,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


# -----------------------------------------------------------------------------
# Summary Translation Endpoint (Phase B)
# -----------------------------------------------------------------------------
class SummaryTranslationRequest(BaseModel):
    target_language: str = Field(default="hi", description="Target ISO language code (e.g. hi, mr, ta)")
    source_language: str = Field(default="en", description="Source ISO language code (e.g. en, hi)")


@router.post("/{id}/summary/translate", response_model=TranslatedSummary)
def translate_case_summary(
    id: str,
    payload: SummaryTranslationRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Translate executive case summary into target regional language."""
    manager = CaseManager(db)
    is_admin = (current_user.role == "admin")
    return manager.translate_case_summary(
        case_id=id,
        target_language=payload.target_language,
        source_language=payload.source_language,
        user_id=current_user.id,
        is_admin=is_admin,
    )



