"""Legal Research Service.

Executes grounded research queries against local verified judgments and bare-act statutes
under strict Hard Rule 4 (zero hallucination, mandatory refusal if ungrounded).
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.agents.legal_research import LegalResearchAgent
from app.schemas.research import LegalResearchInput, LegalResearchOutput
from app.security.audit import record_audit_event
from app.config import get_settings


class ResearchManager:
    """Manages legal research sessions grounded strictly in local database authorities."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.settings = get_settings()

    def execute_research(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        court_filter: Optional[str] = None,
        act_filter: Optional[str] = None,
    ) -> LegalResearchOutput:
        """Execute grounded legal research query across local precedents and statutes."""
        agent = LegalResearchAgent(db_session=self.session)
        inp = LegalResearchInput(
            query=query,
            top_k=top_k,
            court_filter=court_filter,
            act_filter=act_filter,
        )
        output = agent.run(inp)

        record_audit_event(
            event_type="LEGAL_RESEARCH_EXECUTED",
            actor=f"user:{user_id}",
            resource_id=f"query:{hash(query)}",
            input_payload={"query": query, "top_k": top_k, "court": court_filter, "act": act_filter},
            output_payload={"is_refusal": output.is_refusal, "citations_count": len(output.citations)},
            confidence=output.confidence,
            needs_human_review=output.needs_human_review,
            status="SUCCESS",
        )
        return output

