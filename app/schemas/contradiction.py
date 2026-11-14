"""Contradiction report schemas for detecting conflicting statements in depositions/pleadings."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.source import SourceRef
from app.schemas.common import BaseAgentInput, BaseAgentOutput

ContradictionSeverity = Literal["HIGH", "MEDIUM", "LOW"]


class ContradictionItem(BaseModel):
    """Pair of mutually conflicting or divergent statements in legal record."""
    statement_a: str = Field(..., description="First statement assertion")
    statement_b: str = Field(..., description="Second conflicting statement assertion")
    description: str = Field(..., description="Explanation of why the statements contradict each other")
    source_a: SourceRef = Field(..., description="Provenance for first statement")
    source_b: SourceRef = Field(..., description="Provenance for second statement")
    severity: ContradictionSeverity = Field(default="MEDIUM", description="HIGH, MEDIUM, or LOW severity")
    category: Optional[str] = Field(default="FACTUAL_DISCREPANCY", description="Category: ALIBI_CONFLICT, WEAPON_DISCREPANCY, TIME_DISCREPANCY, IDENTITY_CONFLICT, etc.")
    comparison_type: Optional[str] = Field(default="witness_vs_witness", description="Comparison category: witness_vs_witness, statement_vs_fir, fir_vs_chargesheet, same_person_different_times")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class ContradictionReport(BaseAgentOutput):
    """Report detailing factual, deposition, or timeline contradictions."""
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    contradictions: List[ContradictionItem] = Field(default_factory=list)
    has_severe_contradictions: bool = False
    candidate_pairs_evaluated: int = 0
    contradictions_count: int = 0


class ContradictionInput(BaseAgentInput):
    """Input for ContradictionAgent across case documents."""
    case_id: str
    db_session: Optional[object] = None
    facts: Optional[List[object]] = None
    statements: Optional[List[object]] = None
    documents: Optional[dict] = None  # doc_id -> full_text for anti-hallucination snippet checking
