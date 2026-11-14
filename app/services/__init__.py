"""LexAgent Service Layer.

Provides CaseManager, DocumentManager, and ResearchManager to isolate business logic
from API routers.
"""

from app.services.case_manager import CaseManager
from app.services.document_manager import DocumentManager
from app.services.research_manager import ResearchManager

__all__ = ["CaseManager", "DocumentManager", "ResearchManager"]

