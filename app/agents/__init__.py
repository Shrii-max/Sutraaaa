"""Agents package for LexAgent.

Follows Hard Rule 1: Every agent = one class with: typed Pydantic input, typed Pydantic output,
run() method, no hidden global state. Agents talk to each other ONLY through Pydantic schemas in /app/schemas.
"""

from app.agents.base import BaseAgent
from app.agents.ocr import OCRAgent, OCREngine, TesseractOCREngine, FallbackOCREngine
from app.agents.language_detection import LanguageDetectionAgent
from app.agents.document_classifier import (
    DocumentClassifierAgent,
    DocumentClassifierInput,
    DocumentClassifierOutput,
)
from app.agents.fact_extraction import (
    FactExtractionAgent,
    DocumentExtractionInput,
    DocumentExtractionOutput,
)
from app.agents.validation import ValidationAgent, ValidationInput
from app.agents.summary import SummaryAgent, SummaryInput
from app.agents.timeline import TimelineAgent, TimelineInput, LimitationTimelineAgent
from app.agents.statement_index import StatementIndexBuilder, StatementIndexInput
from app.agents.contradiction import ContradictionAgent, ContradictionInput
from app.agents.precedent import PrecedentAnalysisAgent
from app.agents.similar_case import SimilarCaseAgent
from app.agents.legal_research import LegalResearchAgent
from app.agents.legal_risk import LegalRiskAgent
from app.agents.translation import TranslationAgent
from app.agents.voice_brief import VoiceBriefAgent, VoiceQAAgent

__all__ = [
    "BaseAgent",
    "OCRAgent",
    "OCREngine",
    "TesseractOCREngine",
    "FallbackOCREngine",
    "LanguageDetectionAgent",
    "DocumentClassifierAgent",
    "DocumentClassifierInput",
    "DocumentClassifierOutput",
    "FactExtractionAgent",
    "DocumentExtractionInput",
    "DocumentExtractionOutput",
    "ValidationAgent",
    "ValidationInput",
    "SummaryAgent",
    "SummaryInput",
    "TimelineAgent",
    "TimelineInput",
    "LimitationTimelineAgent",
    "StatementIndexBuilder",
    "StatementIndexInput",
    "ContradictionAgent",
    "ContradictionInput",
    "PrecedentAnalysisAgent",
    "SimilarCaseAgent",
    "LegalResearchAgent",
    "LegalRiskAgent",
    "TranslationAgent",
    "VoiceBriefAgent",
    "VoiceQAAgent",
]
