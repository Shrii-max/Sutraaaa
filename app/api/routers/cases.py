"""Cases router: Case file management, document uploads, and case-level intelligence views.

Enforces tenant isolation: lawyers can only access their own cases (admins can access all).
All business logic is delegated to CaseManager and DocumentManager.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import get_current_user, require_lawyer
from app.services.case_manager import CaseManager
from app.services.document_manager import DocumentManager
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

