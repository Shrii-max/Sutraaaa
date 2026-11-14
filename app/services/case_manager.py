"""Case Manager Service.

Encapsulates all case-level legal domain operations, tenant isolation checks,
timeline synthesis, contradiction analysis, and dashboard generation.
"""

import json
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.models import (
    CaseModel,
    DocumentModel,
    FactModel,
    TimelineEventModel,
    ContradictionModel,
    ValidationIssueModel,
    SummaryModel,
    Judgment,
)
from app.agents.statement_index import StatementIndexBuilder
from app.agents.similar_case import SimilarCaseAgent
from app.schemas.precedent import SimilarCaseInput
from app.security.audit import record_audit_event
from app.config import get_settings


class CaseManager:
    """Manages legal case files with strict tenant isolation."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.settings = get_settings()

    def _verify_case_access(self, case: CaseModel, user_id: str, is_admin: bool = False) -> CaseModel:
        """Enforce tenant isolation: lawyer can only access their own cases."""
        if not is_admin and case.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: You do not have permission to access case '{case.id}'.",
            )
        return case

    def create_case(
        self,
        user_id: str,
        title: str,
        case_number: Optional[str] = None,
        court: Optional[str] = None,
    ) -> CaseModel:
        """Create a new legal matter case file."""
        case = CaseModel(
            user_id=user_id,
            title=title.strip(),
            case_number=case_number.strip() if case_number else None,
            court=court.strip() if court else None,
            status="open",
        )
        self.session.add(case)
        self.session.commit()
        self.session.refresh(case)

        record_audit_event(
            event_type="CASE_CREATED",
            actor=f"user:{user_id}",
            resource_id=case.id,
            input_payload={"title": title, "case_number": case_number, "court": court},
            output_payload={"case_id": case.id, "status": "open"},
            status="SUCCESS",
        )
        return case

    def list_cases(self, user_id: str, is_admin: bool = False, limit: int = 50) -> List[CaseModel]:
        """List cases belonging to the authenticated lawyer (or all cases if admin)."""
        stmt = select(CaseModel)
        if not is_admin:
            stmt = stmt.where(CaseModel.user_id == user_id)
        stmt = stmt.order_by(CaseModel.created_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_case(self, case_id: str, user_id: str, is_admin: bool = False) -> CaseModel:
        """Retrieve single case with tenant access verification."""
        case = self.session.get(CaseModel, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case with ID '{case_id}' was not found.",
            )
        return self._verify_case_access(case, user_id, is_admin)

    def get_timeline(self, case_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve chronological timeline events for a case."""
        case = self.get_case(case_id, user_id, is_admin)
        stmt = (
            select(TimelineEventModel)
            .where(TimelineEventModel.case_id == case.id)
            .order_by(TimelineEventModel.event_date.asc())
        )
        events = self.session.execute(stmt).scalars().all()

        timeline_items = []
        for e in events:
            s_ref = {}
            if e.source_ref:
                try:
                    s_ref = json.loads(e.source_ref)
                except Exception:
                    s_ref = {}
            timeline_items.append({
                "id": e.id,
                "date": e.event_date,
                "title": e.title,
                "description": e.description,
                "is_important": e.is_important,
                "confidence": e.confidence,
                "source_ref": s_ref,
            })

        return {
            "case_id": case.id,
            "total_events": len(timeline_items),
            "events": timeline_items,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_statements(self, case_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Build and retrieve indexed victim/witness statements across all case documents."""
        case = self.get_case(case_id, user_id, is_admin)
        builder = StatementIndexBuilder(self.session)
        index = builder.build_index_for_case(case.id)

        return {
            "case_id": case.id,
            "total_statements": index.total_statements,
            "entries": [e.model_dump() for e in index.entries],
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_contradictions(self, case_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve detected contradictions between depositions, FIR, and statements."""
        case = self.get_case(case_id, user_id, is_admin)
        stmt = (
            select(ContradictionModel)
            .where(ContradictionModel.case_id == case.id)
            .order_by(ContradictionModel.created_at.desc())
        )
        contradictions = self.session.execute(stmt).scalars().all()

        items = []
        for c in contradictions:
            items.append({
                "id": c.id,
                "statement_a": c.statement_a,
                "statement_b": c.statement_b,
                "description": c.description,
                "severity": c.severity,
                "confidence": c.confidence,
                "source_a": json.loads(c.source_a) if c.source_a else {},
                "source_b": json.loads(c.source_b) if c.source_b else {},
            })

        return {
            "case_id": case.id,
            "total_contradictions": len(items),
            "contradictions": items,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_similar_cases(self, case_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve precedent cases similar to the current matter (Hard Rule 4: DB verified only)."""
        case = self.get_case(case_id, user_id, is_admin)
        agent = SimilarCaseAgent(db_session=self.session)
        res = agent.run(SimilarCaseInput(case_id=case.id, db_session=self.session))

        return {
            "case_id": case.id,
            "query_fingerprint": res.query_fingerprint,
            "similar_cases": [c.model_dump() for c in res.similar_cases],
            "not_found_message": res.not_found_message,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_dashboard(self, case_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Generate high-level case intelligence dashboard for counsel."""
        case = self.get_case(case_id, user_id, is_admin)

        docs = self.session.execute(
            select(DocumentModel).where(DocumentModel.case_id == case.id)
        ).scalars().all()

        facts_count = self.session.execute(
            select(func.count(FactModel.id)).where(FactModel.case_id == case.id)
        ).scalar() or 0

        pending_reviews_count = self.session.execute(
            select(func.count(FactModel.id)).where(
                FactModel.case_id == case.id,
                FactModel.is_reviewed == False,
                FactModel.confidence < self.settings.CONFIDENCE_THRESHOLD,
            )
        ).scalar() or 0

        timeline_count = self.session.execute(
            select(func.count(TimelineEventModel.id)).where(TimelineEventModel.case_id == case.id)
        ).scalar() or 0

        contradiction_count = self.session.execute(
            select(func.count(ContradictionModel.id)).where(ContradictionModel.case_id == case.id)
        ).scalar() or 0

        # Check high severity validation defects
        high_defects = self.session.execute(
            select(ValidationIssueModel)
            .join(DocumentModel, DocumentModel.id == ValidationIssueModel.document_id)
            .where(
                DocumentModel.case_id == case.id,
                ValidationIssueModel.severity.in_(["HIGH", "CRITICAL"]),
            )
        ).scalars().all()

        return {
            "case_id": case.id,
            "title": case.title,
            "case_number": case.case_number,
            "court": case.court,
            "status": case.status,
            "total_documents": len(docs),
            "documents_summary": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "status": d.status,
                    "page_count": d.page_count,
                    "language": d.detected_language,
                }
                for d in docs
            ],
            "total_facts": facts_count,
            "pending_fact_reviews": pending_reviews_count,
            "timeline_events_count": timeline_count,
            "contradictions_count": contradiction_count,
            "high_severity_defects_count": len(high_defects),
            "needs_counsel_attention": (len(high_defects) > 0 or pending_reviews_count > 0),
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

