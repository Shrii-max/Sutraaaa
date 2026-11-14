"""LangGraph State Definition for LexAgent Orchestration.

Agents communicate exclusively through typed Pydantic models from /app/schemas.
"""

from typing import TypedDict, Optional, List, Annotated
from app.schemas.facts import DocumentExtractionOutput
from app.schemas.timeline import TimelineAnalysisOutput
from app.schemas.precedent import PrecedentSearchOutput
from app.schemas.risks import RiskAnalysisOutput
from app.schemas.dossier import LegalIntelligenceReport


class LegalIntelligenceState(TypedDict, total=False):
    """Execution state passed through the LangGraph agent nodes."""
    document_id: str
    filename: str
    raw_text: str
    extraction_output: Optional[DocumentExtractionOutput]
    timeline_output: Optional[TimelineAnalysisOutput]
    precedent_output: Optional[PrecedentSearchOutput]
    risk_output: Optional[RiskAnalysisOutput]
    final_report: Optional[LegalIntelligenceReport]
    audit_trace_id: Optional[str]
    errors: List[str]

