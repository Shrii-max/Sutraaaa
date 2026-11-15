"""Pydantic v2 schemas for LexAgent Foundation and Pipeline Agents.

Follows Hard Rule 1: Agents talk to each other ONLY through Pydantic schemas in /app/schemas.
"""

from app.schemas.source import SourceRef, SourceReference
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.document import (
    DocumentType,
    DocumentMeta,
    PageOCR,
    OCRResult,
    PageLanguage,
    LanguageResult,
)
from app.schemas.facts import (
    ActCategory,
    StatementType,
    PartyItem,
    DateItem,
    SectionItem,
    AmountItem,
    LocationItem,
    IncidentItem,
    StatementItem,
    ExtractedFacts,
    FactItem,
    DocumentExtractionInput,
    DocumentExtractionOutput,
)
from app.schemas.validation import (
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
)
from app.schemas.contradiction import (
    ContradictionSeverity,
    ContradictionItem,
    ContradictionReport,
    ContradictionInput,
)
from app.schemas.timeline import (
    ImportanceLevel,
    TimelineEvent,
    Timeline,
    DateConflictItem,
    UITimelineItem,
    LimitationCheck,
    TimelineAnalysisInput,
    TimelineAnalysisOutput,
)
from app.schemas.summary import CaseSummary, KeyPoint
from app.schemas.statement import (
    StatementIndexItem,
    StatementIndex,
    StatementIndexInput,
)
from app.schemas.precedent import (
    SimilarCase,
    VerifiedCaseCitation,
    PrecedentMatch,
    PrecedentSearchInput,
    PrecedentSearchOutput,
    SimilarCaseInput,
    SimilarCaseOutput,
)
from app.schemas.research import (
    ResearchCitation,
    LegalResearchInput,
    LegalResearchOutput,
)
from app.schemas.risks import (
    LegalRiskItem,
    RiskAnalysisInput,
    RiskAnalysisOutput,
)
from app.schemas.dossier import LegalIntelligenceReport
from app.schemas.translation import (
    SentenceAlignment,
    TranslationIssue,
    TranslatedPage,
    TranslationInput,
    TranslatedDocument,
    TranslatedSummary,
)
from app.schemas.voice import (
    VoiceBriefInput,
    VoiceBriefOutput,
    VoiceQuestionInput,
    VoiceQuestionOutput,
)

__all__ = [
    "SourceRef",
    "SourceReference",
    "BaseAgentInput",
    "BaseAgentOutput",
    "DocumentType",
    "DocumentMeta",
    "PageOCR",
    "OCRResult",
    "PageLanguage",
    "LanguageResult",
    "ActCategory",
    "StatementType",
    "PartyItem",
    "DateItem",
    "SectionItem",
    "AmountItem",
    "LocationItem",
    "IncidentItem",
    "StatementItem",
    "ExtractedFacts",
    "FactItem",
    "DocumentExtractionInput",
    "DocumentExtractionOutput",
    "IssueSeverity",
    "ValidationIssue",
    "ValidationReport",
    "ContradictionSeverity",
    "ContradictionItem",
    "ContradictionReport",
    "ContradictionInput",
    "ImportanceLevel",
    "TimelineEvent",
    "Timeline",
    "DateConflictItem",
    "UITimelineItem",
    "LimitationCheck",
    "TimelineAnalysisInput",
    "TimelineAnalysisOutput",
    "StatementIndexItem",
    "StatementIndex",
    "StatementIndexInput",
    "CaseSummary",
    "KeyPoint",
    "SimilarCase",
    "VerifiedCaseCitation",
    "PrecedentMatch",
    "PrecedentSearchInput",
    "PrecedentSearchOutput",
    "SimilarCaseInput",
    "SimilarCaseOutput",
    "LegalRiskItem",
    "RiskAnalysisInput",
    "RiskAnalysisOutput",
    "ResearchCitation",
    "LegalResearchInput",
    "LegalResearchOutput",
    "LegalIntelligenceReport",
    "SentenceAlignment",
    "TranslationIssue",
    "TranslatedPage",
    "TranslationInput",
    "TranslatedDocument",
    "TranslatedSummary",
    "VoiceBriefInput",
    "VoiceBriefOutput",
    "VoiceQuestionInput",
    "VoiceQuestionOutput",
]
