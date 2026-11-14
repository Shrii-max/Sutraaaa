"""Case summary schema."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentOutput
from app.schemas.source import SourceRef


class KeyPoint(BaseModel):
    """A key factual or legal takeaway backed by source references."""
    point: str = Field(..., description="Key factual or legal takeaway")
    source_refs: List[SourceRef] = Field(default_factory=list, description="Source references backing this point")


class CaseSummary(BaseAgentOutput):
    """Structured executive summary of a legal case or brief."""
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    summary_text: str = Field(..., min_length=10, description="Executive factual and legal summary (max 150 words)")
    key_points: List[KeyPoint] = Field(default_factory=list, description="Key takeaways, each backed by source refs")
    language: str = Field(default="english", description="Language of summary: english, hindi, or hinglish")
    word_count: int = Field(default=0, description="Total word count of summary_text")
    key_issues: List[str] = Field(default_factory=list, description="Primary legal questions or controversies framed")
    relief_sought: Optional[str] = Field(default=None, description="Prayers or remedies claimed")
