"""Timeline schemas with chronological ordering, date normalization, importance scoring, and conflict detection."""

import uuid
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.source import SourceRef
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.facts import FactItem

ImportanceLevel = Literal["HIGH", "MEDIUM", "LOW"]


class TimelineEvent(BaseModel):
    """Chronological event extracted from legal record with importance flag."""
    event_id: str
    date_str: str = Field(..., description="Date representation (YYYY-MM-DD or as stated in record)")
    normalized_date: Optional[str] = Field(default=None, description="Standardized ISO date (YYYY-MM-DD)")
    event_title: str
    description: str
    importance: ImportanceLevel = Field(default="MEDIUM", description="HIGH, MEDIUM, or LOW importance")
    is_important: bool = Field(default=False, description="Flag indicating critical turning point or cause of action")
    is_cause_of_action: bool = False
    document_id: Optional[str] = None
    source: SourceRef
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class DateConflictItem(BaseModel):
    """Discrepancy where the same event is attributed conflicting dates across different records."""
    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_topic: str = Field(..., description="Topic of the event (e.g. 'occurrence', 'arrest', 'fir')")
    event_title: str = Field(..., description="Title of the conflicting event")
    date_a: str = Field(..., description="First reported date")
    date_b: str = Field(..., description="Second conflicting date")
    doc_id_a: str = Field(..., description="Document ID of first date")
    doc_id_b: str = Field(..., description="Document ID of second date")
    source_a: SourceRef = Field(..., description="Provenance for first date")
    source_b: SourceRef = Field(..., description="Provenance for second date")
    description: str = Field(..., description="Detailed explanation of the chronological conflict")


class UITimelineItem(BaseModel):
    """API-ready JSON shape for rendering interactive timeline in lawyer dashboard."""
    id: str = Field(..., description="Unique event identifier for UI keying")
    date: str = Field(..., description="Normalized date (YYYY-MM-DD)")
    display_date: str = Field(..., description="Human-readable formatted date string")
    title: str = Field(..., description="Concise event headline")
    description: str = Field(..., description="Event synopsis")
    importance: ImportanceLevel = Field(default="MEDIUM", description="HIGH, MEDIUM, or LOW")
    doc_refs: List[str] = Field(default_factory=list, description="Referenced document IDs")
    source_snippets: List[str] = Field(default_factory=list, description="Verbatim textual snippets supporting this event")
    is_conflict: bool = Field(default=False, description="Whether this event is subject to a date discrepancy")
    conflict_notes: Optional[str] = Field(default=None, description="Explanation if conflicting date detected")


class LimitationCheck(BaseModel):
    """Statutory limitation calculation under Indian law."""
    statute: str
    section_or_article: str
    prescribed_period: str
    cause_of_action_date: Optional[str] = None
    limitation_expiry_date: Optional[str] = None
    is_time_barred: bool = False
    delay_condonation_applicable: bool = True
    legal_basis: str


class Timeline(BaseAgentOutput):
    """Chronologically sorted timeline of legal events across case documents."""
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    events: List[TimelineEvent] = Field(default_factory=list)
    ui_timeline: List[UITimelineItem] = Field(default_factory=list, description="API-ready timeline items for UI presentation")
    date_conflicts: List[DateConflictItem] = Field(default_factory=list, description="List of date conflicts detected across documents")
    has_conflicts: bool = Field(default=False, description="True if any conflicting dates exist across documents")

    @model_validator(mode="after")
    def sort_events(self):
        """Ensure events are sorted chronologically by normalized_date or date_str."""
        if self.events:
            self.events.sort(key=lambda e: e.normalized_date or e.date_str or "")
        return self


# Backward-compatible agent extraction schemas
class TimelineAnalysisInput(BaseAgentInput):
    document_id: str
    facts: List[FactItem]


class TimelineAnalysisOutput(BaseAgentOutput):
    document_id: str
    events_chronological: List[TimelineEvent] = Field(default_factory=list)
    cause_of_action_identified: Optional[str] = None
    limitation_assessments: List[LimitationCheck] = Field(default_factory=list)
    has_limitation_risk: bool = False
