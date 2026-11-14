"""Validation report schemas for detecting defects and inconsistencies."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.source import SourceRef
from app.schemas.common import BaseAgentOutput

IssueSeverity = Literal["HIGH", "MEDIUM", "LOW", "CRITICAL"]


class ValidationIssue(BaseModel):
    """An issue, defect, or procedural gap identified in the legal document."""
    severity: IssueSeverity = Field(default="MEDIUM")
    category: str = Field(..., description="e.g. 'LIMITATION', 'JURISDICTION', 'STAMP_DUTY', 'EVIDENCE_65B', 'MISSING_AFFIDAVIT'")
    description: str = Field(..., min_length=3)
    source_refs: List[SourceRef] = Field(default_factory=list, description="Associated source references")
    suggestion: str = Field(..., description="Actionable cure or recommendation for counsel")


class ValidationReport(BaseAgentOutput):
    """Report detailing procedural and statutory validation issues."""
    document_id: str
    issues: List[ValidationIssue] = Field(default_factory=list)
    has_critical_defects: bool = False

