"""Precedent and Similar Case schemas for database-grounded retrieval.

Follows Hard Rule 4: Case law results come ONLY from the database via retrieval.
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.facts import ExtractedFacts


class SimilarCase(BaseModel):
    """Case law match retrieved strictly from local database."""
    case_id: str = Field(..., description="Unique database UUID of precedent judgment")
    title: str = Field(..., description="Official title of the reported case")
    court: str = Field(..., description="Court name (e.g. Supreme Court of India)")
    date: str = Field(..., description="Date of judgment in YYYY-MM-DD or year")
    citation: Optional[str] = Field(default=None, description="Official law report citation")
    url: Optional[str] = Field(default=None, description="Official court record URL or local reference")
    source_url: Optional[str] = Field(default=None, description="Source URL alias")
    outcome: Optional[str] = Field(default=None, description="Disposal outcome (e.g. Allowed, Dismissed, Quashed)")
    matched_paragraph: str = Field(default="", description="Primary matched verbatim text snippet from DB")
    matched_paragraphs: List[str] = Field(default_factory=list, description="All verbatim matched chunk texts from DB")
    score: float = Field(..., ge=0.0, le=1.0, description="Hybrid vector + lexical similarity score")
    why_similar: Optional[str] = Field(default=None, description="Explanation of statutory/factual similarity")
    sections_overlap: List[str] = Field(default_factory=list, description="Common statutory provisions cited")
    fact_overlap: Optional[str] = Field(default=None, description="Description of factual controversy overlap")
    summary: Optional[str] = Field(default=None, description="Strictly grounded summary of retrieved text")


class VerifiedCaseCitation(BaseModel):
    """Case law citation guaranteed to exist in the local verified database."""
    case_db_id: str = Field(..., description="Primary key UUID in local precedent database")
    case_title: str = Field(..., description="Official title as recorded in DB")
    citation: str = Field(..., description="Official citation (e.g. (2021) 5 SCC 123)")
    court: str = Field(..., description="Court name")
    judgment_date: str = Field(..., description="Date of judgment")
    bench: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    db_verified: bool = Field(True, description="Strictly verified in database")


class PrecedentMatch(BaseModel):
    """Retrieved and summarized precedent analysis."""
    case: VerifiedCaseCitation
    relevance_explanation: str
    ratio_decidendi_snippet: str


class PrecedentSearchInput(BaseAgentInput):
    query_text: str
    top_k: int = Field(default=3, ge=1, le=10)
    required_court: Optional[str] = None


class PrecedentSearchOutput(BaseAgentOutput):
    query: str
    matches: List[PrecedentMatch] = Field(default_factory=list)
    similar_cases: List[SimilarCase] = Field(default_factory=list)
    cases_retrieved_count: int = 0
    cases_verified_count: int = 0
    status_summary: str = Field(default="Cases successfully retrieved and verified from DB")


class SimilarCaseInput(BaseAgentInput):
    """Input for SimilarCaseAgent supporting facts-based fingerprinting or direct query."""
    case_id: Optional[str] = None
    query_text: Optional[str] = None
    extracted_facts: Optional[ExtractedFacts] = None
    court: Optional[str] = None
    sections: Optional[List[str]] = None
    year_range: Optional[Tuple[int, int]] = None
    outcome: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=10)
    score_threshold: float = Field(default=0.01)
    summarize_with_llm: bool = True


class SimilarCaseOutput(BaseAgentOutput):
    """Result of similar case search with database-verified precedent cases."""
    case_id: Optional[str] = None
    fingerprint_query: str = ""
    similar_cases: List[SimilarCase] = Field(default_factory=list)
    total_found: int = 0
    message: str = Field(default="Similar cases successfully retrieved and verified from DB")
