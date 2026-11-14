"""Synthesized Legal Intelligence Dossier schema."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentOutput
from app.schemas.facts import DocumentExtractionOutput
from app.schemas.timeline import TimelineAnalysisOutput
from app.schemas.precedent import PrecedentSearchOutput
from app.schemas.risks import RiskAnalysisOutput


class LegalIntelligenceReport(BaseAgentOutput):
    """Unified legal intelligence dossier returned by the multi-agent orchestrator."""
    case_summary: str = Field(..., description="Objective case summary based on verifiable facts")
    document_extraction: DocumentExtractionOutput
    timeline_analysis: TimelineAnalysisOutput
    precedents: PrecedentSearchOutput
    risk_assessment: RiskAnalysisOutput
    strategic_recommendations: List[str] = Field(
        default_factory=list,
        description="Suggested advocacy points, filings, or defect cures for counsel consideration",
    )
    audit_trace_id: str = Field(..., description="Append-only audit record identifier")

