"""Schemas for LegalResearchAgent covering grounded research across judgments and bare-act statutes."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentInput, BaseAgentOutput


class ResearchCitation(BaseModel):
    """Citation to an authoritative passage retrieved from the local database."""
    source_type: Literal["judgment", "statute", "constitution"]
    id: str = Field(..., description="Database ID of judgment chunk or statute section")
    title_or_act: str = Field(..., description="Judgment title or Statute act name")
    citation_or_section: str = Field(..., description="Law report citation or Section number")
    verbatim_snippet: str = Field(..., description="Verbatim matched text snippet from the database")
    source_url: Optional[str] = None
    pdf_page: Optional[int] = None
    score: float = Field(default=1.0, ge=0.0, le=1.0)


class LegalResearchInput(BaseAgentInput):
    """Input for free-text legal research query."""
    query: str = Field(..., min_length=3, description="Free-text legal question or research query")
    include_judgments: bool = Field(default=True, description="Search across judicial precedents")
    include_statutes: bool = Field(default=True, description="Search across bare-act statutes")
    court_filter: Optional[str] = None
    act_filter: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=15)
    score_threshold: float = Field(default=0.01)


class LegalResearchOutput(BaseAgentOutput):
    """Grounded legal research response backed exclusively by retrieved authorities."""
    query: str
    answer: str = Field(..., description="Grounded answer based strictly on retrieved chunks")
    citations: List[ResearchCitation] = Field(default_factory=list, description="Citations to retrieved chunks only")
    is_refusal: bool = Field(default=False, description="True if query was refused due to lack of relevant authorities in DB")
    refusal_reason: Optional[str] = None

