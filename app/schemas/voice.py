"""Pydantic Schemas for LexAgent Voice Delivery (Phase C).

Covers spoken case briefs and grounded spoken question answering.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.source import SourceRef


class VoiceBriefInput(BaseAgentInput):
    """Input parameters for generating a spoken legal case brief."""
    case_id: str = Field(..., description="Unique ID of the legal matter case file")
    depth: str = Field(default="2min", description="Brief depth: '30s', '2min', or 'full'")
    language: str = Field(default="en", description="Target language code: 'en', 'hi', or 'mr'")
    voice_id: Optional[str] = Field(default=None, description="Voice model identifier in VoiceFlow")


class VoiceBriefOutput(BaseAgentOutput):
    """Generated spoken legal brief with clean spoken script and audio."""
    case_id: str = Field(..., description="Case matter identifier")
    depth: str = Field(..., description="Depth tier: '30s', '2min', or 'full'")
    language: str = Field(default="en", description="Spoken language code")
    spoken_script: str = Field(..., description="Expanded, symbol-free spoken script")
    audio_base64: Optional[str] = Field(default=None, description="Base64 encoded WAV audio bytes")
    duration_estimate_sec: int = Field(default=120, description="Estimated duration of spoken script in seconds")
    source_refs: List[SourceRef] = Field(default_factory=list, description="Verifiable document provenance citations")
    disclaimer: str = Field(
        default="This is an artificial intelligence decision-support brief for advocates, not formal legal advice.",
        description="Mandatory spoken and textual legal disclaimer",
    )


class VoiceQuestionInput(BaseAgentInput):
    """Inquiry from advocate delivered via voice audio or text."""
    case_id: str = Field(..., description="Target case matter identifier")
    question_text: Optional[str] = Field(default=None, description="Direct text of the advocate's legal query")
    audio_base64: Optional[str] = Field(default=None, description="Base64-encoded raw audio question")
    language: str = Field(default="en", description="Spoken inquiry language: 'en', 'hi', 'mr'")


class VoiceQuestionOutput(BaseAgentOutput):
    """Grounded spoken response or explicit refusal."""
    case_id: str = Field(..., description="Case matter identifier")
    transcribed_question: str = Field(..., description="User's transcribed question")
    spoken_answer: str = Field(..., description="Grounded spoken response script")
    is_refusal: bool = Field(default=False, description="True if inquiry was refused due to lack of case grounding")
    refusal_reason: Optional[str] = Field(default=None, description="Audit reason for refusal")
    audio_base64: Optional[str] = Field(default=None, description="Synthesized audio answer base64")
    source_refs: List[SourceRef] = Field(default_factory=list, description="Grounding source references from case record")
    disclaimer: str = Field(
        default="This answer is generated for decision support based strictly on case records on file.",
        description="Mandatory statutory legal disclaimer",
    )
