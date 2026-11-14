"""Facts router: Lawyer fact review and human-in-the-loop correction."""

from typing import Optional, Dict, Any, Literal
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import require_lawyer
from app.services.document_manager import DocumentManager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/facts", tags=["Fact Review & Corrections"])


class FactReviewRequest(BaseModel):
    action: Literal["approved", "corrected", "rejected"] = Field(
        ...,
        description="Review decision: 'approved', 'corrected', or 'rejected'",
        json_schema_extra={"example": "corrected"},
    )
    correction_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Corrected fact attributes if action is 'corrected'",
        json_schema_extra={"example": {"value": 2500000.0, "notes": "Verified against original bank statement"}},
    )


class FactReviewResponse(BaseModel):
    fact_id: str
    is_reviewed: bool
    reviewed_by: str
    review_action: str
    correction_data: Optional[Dict[str, Any]] = None
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.post("/{id}/review", response_model=FactReviewResponse)
def review_fact(
    id: str,
    req: FactReviewRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Lawyer approves, corrects, or rejects an extracted fact. Stores the correction and audit trail."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    res = manager.review_fact(
        fact_id=id,
        user_id=current_user.id,
        action=req.action,
        correction_data=req.correction_data,
        is_admin=is_admin,
    )
    return FactReviewResponse(**res)

