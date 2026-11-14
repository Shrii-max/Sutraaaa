"""Extracted legal facts schemas for Indian litigation.

Follows Hard Rule 2: Every item has SourceRef + confidence.
No source = rejected.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.source import SourceRef
from app.schemas.common import BaseAgentInput, BaseAgentOutput

ActCategory = Literal["IPC", "BNS", "CrPC", "BNSS", "other"]
StatementType = Literal["161", "164", "complaint", "deposition", "other"]


class PartyItem(BaseModel):
    name: str = Field(..., min_length=1)
    role: str = Field(..., description="e.g. 'plaintiff', 'defendant', 'accused', 'complainant', 'witness'")
    source: SourceRef = Field(..., description="Mandatory source provenance")
    confidence: float = Field(..., ge=0.0, le=1.0)


class DateItem(BaseModel):
    date_str: str = Field(..., description="Date mentioned in document")
    description: str = Field(..., description="Context of the date (e.g. date of agreement, date of dishonour)")
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class SectionItem(BaseModel):
    act: ActCategory = Field(default="other", description="IPC, BNS, CrPC, BNSS, or other statutory act")
    section_number: str = Field(..., description="e.g. '420', '302', '138', '113'")
    description: str = Field(..., description="Short explanation of legal provision invoked")
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class AmountItem(BaseModel):
    value: float = Field(..., description="Numerical monetary value")
    currency: str = Field(default="INR", description="Currency (default INR)")
    context: str = Field(..., description="e.g. 'loan advance', 'cheque amount', 'damages claim'")
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class LocationItem(BaseModel):
    place: str = Field(..., description="Geographical name, court jurisdiction, or police station")
    context: str = Field(..., description="e.g. 'place of contract signing', 'crime scene', 'drawee bank branch'")
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class IncidentItem(BaseModel):
    title: str = Field(..., description="Short title of incident")
    description: str = Field(..., description="Detailed factual assertion of incident")
    date: Optional[str] = None
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class StatementItem(BaseModel):
    statement_type: StatementType = Field(
        ...,
        description="Type of testimony/statement: Section 161 CrPC, Section 164 CrPC, complaint, deposition, or other",
    )
    speaker: str = Field(..., description="Person who made the statement")
    role: str = Field(..., description="Role of the speaker (e.g. complainant, witness, accused)")
    recorded_on: Optional[str] = None
    recorded_by: Optional[str] = None
    content: str = Field(..., min_length=1, description="Verbatim or summarized statement")
    source: SourceRef
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExtractedFacts(BaseModel):
    """Unified collection of structured legal facts extracted with mandatory provenance."""
    parties: List[PartyItem] = Field(default_factory=list)
    dates: List[DateItem] = Field(default_factory=list)
    sections: List[SectionItem] = Field(default_factory=list)
    amounts: List[AmountItem] = Field(default_factory=list)
    locations: List[LocationItem] = Field(default_factory=list)
    incidents: List[IncidentItem] = Field(default_factory=list)
    statements: List[StatementItem] = Field(default_factory=list)
    purpose: Optional[str] = Field(default=None, description="Primary legal objective of document")
    court: Optional[str] = Field(default=None, description="Named judicial forum")
    case_number: Optional[str] = Field(default=None, description="Official filing or suit number")


# Backward-compatible agent extraction models
class FactItem(BaseModel):
    fact_id: str
    category: str
    statement: str
    entities_involved: List[str] = Field(default_factory=list)
    date_mentioned: Optional[str] = None
    source: SourceRef


class DocumentExtractionInput(BaseAgentInput):
    document_id: str
    text_content: str
    filename: str = "document.pdf"
    language_hint: Optional[str] = "mixed"


class DocumentExtractionOutput(BaseAgentOutput):
    document_id: str
    detected_language: str
    parties_plaintiff: List[str] = Field(default_factory=list)
    parties_defendant: List[str] = Field(default_factory=list)
    court_name: Optional[str] = None
    case_number: Optional[str] = None
    facts: List[FactItem] = Field(default_factory=list)
    extracted_facts: Optional[ExtractedFacts] = None
    rejected_facts_count: int = 0
