"""Case Law Verifier.

Enforces Hard Rule 4:
Case law / similar-case results must come ONLY from the database via retrieval.
The LLM must NEVER generate, recall, or invent case names, citations or judgments.
LLM may only summarize text that retrieval returned, and every cited case id must be
verified to exist in DB before output. If nothing is found, return "not found".
"""

from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import PrecedentCaseModel
from app.schemas.precedent import VerifiedCaseCitation


class VerifiedCaseResult(BaseModel):
    is_valid: bool
    case: Optional[VerifiedCaseCitation] = None
    rejection_reason: Optional[str] = None


class CaseLawVerifier:
    """Verifies that any case cited or retrieved exists verbatim in the local database."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def verify_case_id(self, case_id: str, similarity_score: float = 1.0) -> VerifiedCaseResult:
        """Verify whether a case ID exists in the precedent database."""
        case_record = self.session.get(PrecedentCaseModel, case_id)
        if not case_record:
            return VerifiedCaseResult(
                is_valid=False,
                rejection_reason=f"Case ID '{case_id}' does not exist in local verified database",
            )

        citation = VerifiedCaseCitation(
            case_db_id=str(case_record.id),
            case_title=case_record.case_title,
            citation=case_record.citation,
            court=case_record.court,
            judgment_date=case_record.judgment_date,
            bench=case_record.bench,
            similarity_score=round(similarity_score, 4),
            db_verified=True,
        )
        return VerifiedCaseResult(is_valid=True, case=citation)

    def verify_citation_string(self, citation_str: str) -> VerifiedCaseResult:
        """Verify whether a citation string matches an exact DB record."""
        stmt = select(PrecedentCaseModel).where(
            PrecedentCaseModel.citation.ilike(citation_str.strip())
        )
        record = self.session.execute(stmt).scalars().first()
        if not record:
            return VerifiedCaseResult(
                is_valid=False,
                rejection_reason=f"Citation '{citation_str}' not found in local verified database",
            )

        citation = VerifiedCaseCitation(
            case_db_id=str(record.id),
            case_title=record.case_title,
            citation=record.citation,
            court=record.court,
            judgment_date=record.judgment_date,
            bench=record.bench,
            similarity_score=1.0,
            db_verified=True,
        )
        return VerifiedCaseResult(is_valid=True, case=citation)

    def filter_and_verify_candidates(
        self, candidate_cases: List[PrecedentCaseModel]
    ) -> List[VerifiedCaseCitation]:
        """Strictly verify every candidate case against DB records and filter out any unverified cases."""
        verified_citations: List[VerifiedCaseCitation] = []
        for case in candidate_cases:
            res = self.verify_case_id(str(case.id))
            if res.is_valid and res.case:
                verified_citations.append(res.case)
        return verified_citations

