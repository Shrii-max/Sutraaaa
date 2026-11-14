"""Source reference schema for verifiable factual provenance.

Follows Hard Rule 2: Every extracted fact MUST carry a source reference:
{document_id, page, char_start, char_end, snippet}. No source = fact is rejected.
"""

from pydantic import BaseModel, Field, field_validator


class SourceRef(BaseModel):
    """Mandatory provenance reference for any extracted fact or legal assertion."""
    document_id: str = Field(..., description="Unique identifier of source document")
    page: int = Field(..., ge=1, description="1-indexed page number in the source file")
    char_start: int = Field(..., ge=0, description="Start character offset on the page")
    char_end: int = Field(..., ge=0, description="End character offset on the page")
    snippet: str = Field(..., min_length=1, description="Verbatim text snippet from document")

    @field_validator("char_end")
    @classmethod
    def validate_range(cls, v: int, info) -> int:
        start = info.data.get("char_start")
        if start is not None and v <= start:
            raise ValueError(f"char_end ({v}) must be greater than char_start ({start})")
        return v

    @field_validator("snippet")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Source snippet cannot be empty or only whitespace")
        return cleaned


# Backward-compatible alias
SourceReference = SourceRef
