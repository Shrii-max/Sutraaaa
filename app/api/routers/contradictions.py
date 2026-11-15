"""Contradictions router: Lawyer review and feedback loop for detected evidentiary contradictions.

Enforces v2 Requirement:
Store lawyer accept/reject feedback table and expose POST /contradictions/{id}/feedback.
"""

from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import ContradictionModel, CaseModel, UserModel
from app.security.jwt import get_current_user, require_lawyer
from app.security.audit import record_audit_event
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/contradictions", tags=["Contradictions"])


class ContradictionFeedbackRequest(BaseModel):
    verdict: Literal["ACCEPTED", "REJECTED", "IGNORED"] = Field(
        ...,
        description="Advocate verdict on whether the detected contradiction is genuine or a false alarm",
        json_schema_extra={"example": "ACCEPTED"},
    )
    notes: Optional[str] = Field(
        None,
        description="Reasoning or notes from counsel",
        json_schema_extra={"example": "Verified in cross-examination; key alibi conflict"},
    )


class ContradictionFeedbackResponse(BaseModel):
    contradiction_id: str
    case_id: str
    lawyer_verdict: str
    status: str = "feedback_recorded"
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.post("/{id}/feedback", response_model=ContradictionFeedbackResponse)
def submit_contradiction_feedback(
    id: str,
    payload: ContradictionFeedbackRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Advocate feedback on whether a detected contradiction is valid or a false alarm."""
    stmt = select(ContradictionModel).where(ContradictionModel.id == id)
    contradiction = db.scalar(stmt)
    if not contradiction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contradiction '{id}' not found.")

    # Tenant isolation check
    if current_user.role != "admin" and contradiction.case_id:
        case = db.scalar(select(CaseModel).where(CaseModel.id == contradiction.case_id))
        if case and case.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this case contradiction.")

    contradiction.lawyer_verdict = payload.verdict
    contradiction.lawyer_feedback_notes = payload.notes
    db.commit()
    db.refresh(contradiction)

    record_audit_event(
        event_type="CONTRADICTION_FEEDBACK",
        actor=f"user:{current_user.email}",
        resource_id=id,
        input_payload={"verdict": payload.verdict, "notes": payload.notes},
        output_payload={"status": "feedback_recorded"},
        confidence=1.0,
        needs_human_review=False,
        status="SUCCESS",
    )

    return ContradictionFeedbackResponse(
        contradiction_id=contradiction.id,
        case_id=contradiction.case_id or "",
        lawyer_verdict=contradiction.lawyer_verdict,
        status="feedback_recorded",
        disclaimer=settings.DISCLAIMER_TEXT,
    )

