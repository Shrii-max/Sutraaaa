"""Schemas for Multilingual Document & Summary Translation (LexAgent Phase B).

Enforces sentence-level SourceRef alignment, protected token integrity,
and back-translation verification flags.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.source import SourceRef


class SentenceAlignment(BaseModel):
    """Bilingual sentence-level alignment with exact source provenance."""
    source_sentence: str = Field(..., description="Original source sentence")
    target_sentence: str = Field(..., description="Translated target sentence")
    source_ref: SourceRef = Field(..., description="SourceRef mapping to the original page and character range")


class TranslationIssue(BaseModel):
    """Quality or safety defect detected during translation or back-translation."""
    category: str = Field(..., description="Issue category: back_translation_divergence, protected_token_missing, glossary_mismatch, etc.")
    severity: str = Field(default="MEDIUM", description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")
    description: str = Field(..., description="Detailed explanation of the translation divergence or risk")
    source_snippet: Optional[str] = Field(default=None, description="Problematic snippet from the source text")


class TranslatedPage(BaseModel):
    """Translated page contents with sentence alignments."""
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    source_text: str = Field(..., description="Original page text")
    translated_text: str = Field(..., description="Translated page text")
    alignments: List[SentenceAlignment] = Field(default_factory=list, description="Sentence-by-sentence alignments")


class TranslationInput(BaseAgentInput):
    """Input payload for TranslationAgent."""
    document_id: Optional[str] = Field(default=None, description="Document ID if translating a document")
    case_id: Optional[str] = Field(default=None, description="Case ID if translating case-level artifact")
    content: Optional[str] = Field(default=None, description="Raw text to translate (for single-block or summary translation)")
    pages_data: Optional[List[dict]] = Field(
        default=None,
        description="List of page dicts [{'page_number': int, 'text': str}] for full document translation",
    )
    source_language: str = Field(default="en", description="Source ISO language code (e.g. en, hi, mr)")
    target_language: str = Field(default="hi", description="Target ISO language code (e.g. hi, mr, ta, bn)")
    preserve_glossary: bool = Field(default=True, description="Strictly preserve statutory legal terminology")
    verify_backtranslation: bool = Field(default=True, description="Run back-translation consistency check")


class TranslatedDocument(BaseAgentOutput):
    """Complete translated document with sentence-level SourceRefs."""
    document_id: str = Field(..., description="Unique identifier of translated document")
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(..., description="Target language code")
    pages: List[TranslatedPage] = Field(default_factory=list, description="Translated pages with alignments")
    full_translated_text: str = Field(..., description="Concatenated translated document text")
    issues: List[TranslationIssue] = Field(default_factory=list, description="Divergence and quality issues flagged")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 fingerprint for caching")
    disclaimer: str = Field(
        default="Machine translation, not an official court translation. For decision-support only.",
        description="Mandatory translation safety disclaimer",
    )


class TranslatedSummary(BaseAgentOutput):
    """Translated case or document summary."""
    case_id: Optional[str] = Field(default=None, description="Case ID if case-level summary")
    document_id: Optional[str] = Field(default=None, description="Document ID if document-level summary")
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(..., description="Target language code")
    original_summary: str = Field(..., description="Original summary text in source language")
    translated_summary: str = Field(..., description="Translated summary text in target language")
    issues: List[TranslationIssue] = Field(default_factory=list, description="Divergence and quality issues flagged")
    disclaimer: str = Field(
        default="Machine translation, not an official court translation. For decision-support only.",
        description="Mandatory translation safety disclaimer",
    )

