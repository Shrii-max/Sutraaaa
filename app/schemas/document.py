"""Document metadata, OCR result, and Language detection schemas."""

from typing import List, Literal, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

DocumentType = Literal[
    "FIR",
    "petition",
    "judgment",
    "affidavit",
    "witness_statement",
    "order",
    "other",
]


class DocumentMeta(BaseModel):
    """Metadata describing an ingested legal document."""
    doc_id: str = Field(..., description="Unique document ID (UUID)")
    filename: str = Field(..., description="Original filename")
    doc_type: DocumentType = Field(default="other", description="Classified legal document category")
    languages: List[str] = Field(default_factory=lambda: ["en"], description="List of detected languages (e.g. en, hi)")
    page_count: int = Field(default=1, ge=1, description="Total number of pages")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sha256_hash: Optional[str] = None


class PageOCR(BaseModel):
    """Text and confidence extracted for a single page."""
    page_number: int = Field(..., ge=1)
    text: str = Field(..., description="Extracted textual content on this page")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Per-page OCR extraction confidence")


class OCRResult(BaseModel):
    """Overall OCR extraction result across document pages."""
    document_id: str
    pages: List[PageOCR] = Field(default_factory=list)
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PageLanguage(BaseModel):
    """Language and script detected for a specific page."""
    page_number: int = Field(..., ge=1)
    language: str = Field(..., description="e.g. 'hindi', 'english', 'hinglish'")
    script: str = Field(..., description="e.g. 'Devanagari', 'Latin'")


class LanguageResult(BaseModel):
    """Multilingual script and language classification across document pages."""
    document_id: str
    pages: List[PageLanguage] = Field(default_factory=list)
    primary_language: str = Field(default="english")

