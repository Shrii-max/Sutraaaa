"""Documents router: Per-document intelligence inspections.

Endpoints:
  GET /documents/{id}/status
  GET /documents/{id}/summary
  GET /documents/{id}/facts
  GET /documents/{id}/validation
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import require_lawyer
from app.services.document_manager import DocumentManager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["Document Intelligence"])


@router.get("/{id}/status")
def get_document_status(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get per-step execution status (pending, running, done, failed, needs_review) and crash recovery state."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_status(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/summary")
def get_document_summary(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get concise executive summary and key points with SourceRefs."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_summary(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/facts")
def get_document_facts(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get extracted facts with mandatory provenance (document_id, page, offsets, snippet) and review state."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_facts(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/validation")
def get_document_validation(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get statutory validation defects, chronological anomalies, and missing verification issues."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_validation(document_id=id, user_id=current_user.id, is_admin=is_admin)

