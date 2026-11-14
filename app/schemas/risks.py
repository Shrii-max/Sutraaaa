"""Legal and procedural risk analysis schemas for Indian litigation."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.facts import FactItem
from app.schemas.timeline import TimelineAnalysisOutput


class LegalRiskItem(BaseModel):
    """Specific procedural, jurisdictional or evidentiary risk."""
    risk_id: str
    category: str = Field(
        ...,
        description="Category: 'JURISDICTION', 'LIMITATION', 'PROCEDURAL_DEFECT', 'EVIDENTIARY_DEFECT', 'STAMP_DUTY', 'STATUTORY_COMPLIANCE'",
    )
    severity: str = Field(..., description="HIGH, MEDIUM, or LOW")
    statutory_provision: str = Field(
        ...,
        description="Relevant law (e.g., 'CPC Order VII Rule 11', 'Section 65B Evidence Act / Section 63 BSA', 'Section 35 Indian Stamp Act')",
    )
    issue_description: str
    mitigation_strategy: str


class RiskAnalysisInput(BaseAgentInput):
    """Input for Risk Analysis Agent."""
    document_id: str
    facts: List[FactItem]
    timeline_analysis: Optional[TimelineAnalysisOutput] = None


class RiskAnalysisOutput(BaseAgentOutput):
    """Output from Risk Analysis Agent."""
    document_id: str
    risks: List[LegalRiskItem] = Field(default_factory=list)
    overall_risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    procedural_defects_found: bool = False
    evidence_defects_found: bool = False

