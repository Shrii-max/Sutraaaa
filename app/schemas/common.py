"""Common base schemas for all LexAgent agents and responses.

Follows Hard Rule 3: Every agent output carries confidence (0-1) and needs_human_review (bool).
Follows Hard Rule 10: Output is decision-support for lawyers, never legal advice. Add a disclaimer field.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from app.config import get_settings


class BaseAgentInput(BaseModel):
    """Base schema for all typed agent inputs."""
    request_id: Optional[str] = Field(default=None, description="Correlation ID for audit trace")


class BaseAgentOutput(BaseModel):
    """Base schema for all typed agent outputs ensuring consistent safety & audit fields."""
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 based on verification and completeness",
    )
    needs_human_review: bool = Field(
        ...,
        description="Flag indicating manual review by an advocate is required before relying on this output",
    )
    disclaimer: str = Field(
        default_factory=lambda: get_settings().DISCLAIMER_TEXT,
        description="Mandatory statutory and advisory disclaimer",
    )
    audit_notes: Optional[str] = Field(
        default=None,
        description="Reasoning trail or warning notes recorded during agent execution",
    )
    engine: str = Field(
        default="rules",
        description="Engine actually used: regex | rules | llm | nli | embedder | tesseract | pymupdf | tts",
    )
    llm_called: bool = Field(
        default=False,
        description="Whether an LLM model was invoked during this agent run",
    )
    fallback_taken: bool = Field(
        default=False,
        description="Whether fallback logic was taken due to service unavailability or failure",
    )
    status: Literal["live_model", "rule_based", "fallback", "failed", "needs_review"] = Field(
        default="rule_based",
        description="Honest operational status of this agent output",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Explicit error explanation if the engine or model was unreachable",
    )

