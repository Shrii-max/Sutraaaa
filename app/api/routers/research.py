"""Legal Research router: Grounded question answering across judicial precedents and bare-act statutes."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import require_lawyer, get_optional_lawyer
from app.services.research_manager import ResearchManager
from app.schemas.research import ResearchCitation
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/research", tags=["Legal Research"])


class ResearchQueryRequest(BaseModel):
    query: str = Field(
        ...,
        description="Free-text legal question for Indian statutory and judicial retrieval",
        json_schema_extra={"example": "What are the essential ingredients for Section 420 IPC and regular bail considerations?"},
    )
    top_k: int = Field(default=5, ge=1, le=20, json_schema_extra={"example": 5})
    court_filter: Optional[str] = Field(None, json_schema_extra={"example": "Supreme Court of India"})
    act_filter: Optional[str] = Field(None, json_schema_extra={"example": "IPC"})


class ResearchQueryResponse(BaseModel):
    query: str
    answer: str = Field(..., description="Grounded legal explanation citing verified database excerpts")
    citations: List[ResearchCitation]
    is_refusal: bool = Field(False, description="True if no relevant authorities were found in the database (Hard Rule 4)")
    refusal_reason: Optional[str] = None
    confidence: float
    needs_human_review: bool
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.post("", response_model=ResearchQueryResponse)
def conduct_legal_research(
    req: ResearchQueryRequest,
    current_user: UserModel = Depends(get_optional_lawyer),
    db: Session = Depends(get_db),
):
    """Execute grounded legal research over local judgments and bare-act statutes (Hard Rule 4: DB verified only)."""
    manager = ResearchManager(db)
    res = manager.execute_research(
        query=req.query,
        user_id=current_user.id,
        top_k=req.top_k,
        court_filter=req.court_filter,
        act_filter=req.act_filter,
    )
    return ResearchQueryResponse(
        query=res.query,
        answer=res.answer,
        citations=res.citations,
        is_refusal=res.is_refusal,
        refusal_reason=res.refusal_reason,
        confidence=res.confidence,
        needs_human_review=res.needs_human_review,
        disclaimer=settings.DISCLAIMER_TEXT,
    )

