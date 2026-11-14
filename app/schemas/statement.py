"""Statement Index schema for case-level indexing of victim and witness statements."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.source import SourceRef
from app.schemas.common import BaseAgentInput, BaseAgentOutput


class StatementIndexItem(BaseModel):
    """View of an individual victim or witness statement recorded in the case."""
    statement_id: str = Field(..., description="Unique statement identifier")
    speaker: str = Field(..., description="Who made the statement (deponent, witness, victim, complainant)")
    role: str = Field(..., description="Role of the speaker (e.g. 'victim', 'eye_witness', 'panch_witness', 'accused', 'investigating_officer')")
    recorded_on: Optional[str] = Field(default=None, description="When recorded (normalized date YYYY-MM-DD or original format)")
    recorded_by: Optional[str] = Field(default=None, description="By whom (IO, Police Station, Magistrate, Court)")
    section: str = Field(default="Section 161 CrPC", description="Statutory provision: Section 161 CrPC / 180 BNSS, Section 164 CrPC / 183 BNSS, complaint, deposition")
    summary: str = Field(..., description="Short content summary of the statement")
    content: str = Field(default="", description="Verbatim content or excerpt of the testimony")
    document_id: str = Field(..., description="Document ID where statement was found")
    source_ref: SourceRef = Field(..., description="Verbatim source reference provenance")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)


class StatementIndex(BaseAgentOutput):
    """Case-level catalog and indexed view of all victim and witness statements."""
    case_id: str
    statements: List[StatementIndexItem] = Field(default_factory=list)
    total_statements: int = 0
    victim_count: int = 0
    witness_count: int = 0


class StatementIndexInput(BaseAgentInput):
    """Input parameters for StatementIndexBuilder."""
    case_id: str
    db_session: Optional[object] = None
    statements: Optional[List[object]] = None
    facts: Optional[List[object]] = None

