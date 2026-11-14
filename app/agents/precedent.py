"""Precedent Analysis and Verification Agent.

Follows Hard Rule 4: Case law / similar-case results must come ONLY from the database via retrieval.
The LLM must NEVER generate, recall, or invent case names, citations or judgments.
LLM may only summarize text that retrieval returned, and every cited case id must be
verified to exist in DB before output. If nothing is found, return "not found".
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.schemas.precedent import (
    PrecedentMatch,
    VerifiedCaseCitation,
    PrecedentSearchInput,
    PrecedentSearchOutput,
)
from app.retrieval.retriever import HybridRetriever
from app.retrieval.verifier import CaseLawVerifier


class _CaseSummaryItem(BaseModel):
    case_db_id: str
    relevance_explanation: str
    ratio_decidendi_snippet: str


class _LLMPrecedentSummaryResponse(BaseModel):
    summaries: List[_CaseSummaryItem] = Field(default_factory=list)
    confidence: float = 0.90


class PrecedentAnalysisAgent(BaseAgent[PrecedentSearchInput, PrecedentSearchOutput]):
    """Retrieves and summarizes verified Indian precedent cases strictly from local DB."""

    agent_name: str = "PrecedentAnalysisAgent"

    def __init__(self, db_session: Session, llm_client=None):
        super().__init__(llm_client=llm_client)
        self.session = db_session
        self.retriever = HybridRetriever(db_session)
        self.verifier = CaseLawVerifier(db_session)

    def _execute(self, input_data: PrecedentSearchInput) -> PrecedentSearchOutput:
        # Step 1: Retrieve candidate precedents ONLY from the local database
        candidates = self.retriever.search_precedents(
            query=input_data.query_text,
            top_k=input_data.top_k,
            court_filter=input_data.required_court,
        )

        # Step 2: Strictly verify every candidate against local DB records
        verified_citations = self.verifier.filter_and_verify_candidates(candidates)

        # Hard Rule 4: If nothing is found in DB, return "not found"
        if not verified_citations:
            return PrecedentSearchOutput(
                query=input_data.query_text,
                matches=[],
                cases_retrieved_count=0,
                cases_verified_count=0,
                status_summary="not found",
                confidence=1.0,
                needs_human_review=False,
                audit_notes="No precedent cases matched the query in the local verified database.",
            )

        # Step 3: Provide ONLY verified DB content to LLM for strictly grounded summarization
        db_records_prompt_block = "\n\n".join([
            f"--- Case ID: {c.case_db_id} ---\n"
            f"Title: {c.case_title}\n"
            f"Citation: {c.citation}\n"
            f"Court: {c.court} ({c.judgment_date})\n"
            f"Summary from DB: {cand.summary}\n"
            f"Ratio Decidendi from DB: {cand.ratio_decidendi}"
            for c, cand in zip(verified_citations, candidates)
        ])

        prompt = (
            f"Legal Query / Facts:\n\"{input_data.query_text}\"\n\n"
            f"VERIFIED DATABASE RECORDS (ONLY SOURCE PERMITTED):\n{db_records_prompt_block}\n\n"
            f"INSTRUCTIONS:\n"
            f"Summarize the relevance and legal principle for each case above relative to the query. "
            f"STRICT PROHIBITION: You must NEVER invent, recall, or introduce any other cases or citations. "
            f"Only summarize the exact cases listed above by matching case_db_id."
        )

        system = (
            "You are a judicial research assistant. You are strictly forbidden from citing any case "
            "not explicitly given in the user prompt. Summarize only provided records."
        )

        llm_response, review_needed = self.llm.generate_structured(
            prompt=prompt,
            schema=_LLMPrecedentSummaryResponse,
            system=system,
        )

        # Step 4: Double-verify each summary before creating output
        # Map DB ID to verified citation
        citation_by_id = {c.case_db_id: c for c in verified_citations}
        candidate_by_id = {str(cand.id): cand for cand in candidates}
        final_matches: List[PrecedentMatch] = []

        for item in llm_response.summaries:
            target_id = item.case_db_id
            if target_id in citation_by_id:
                final_matches.append(
                    PrecedentMatch(
                        case=citation_by_id[target_id],
                        relevance_explanation=item.relevance_explanation,
                        ratio_decidendi_snippet=item.ratio_decidendi_snippet,
                    )
                )

        # Fallback: if LLM failed to include all verified cases in summaries, include default summary from DB
        for cit in verified_citations:
            if not any(m.case.case_db_id == cit.case_db_id for m in final_matches):
                cand = candidate_by_id.get(cit.case_db_id)
                ratio_snippet = cand.ratio_decidendi if cand else "Binding principle from DB."
                summary_text = cand.summary if cand else "Verified DB precedent."
                final_matches.append(
                    PrecedentMatch(
                        case=cit,
                        relevance_explanation=summary_text,
                        ratio_decidendi_snippet=ratio_snippet,
                    )
                )

        confidence = llm_response.confidence
        return PrecedentSearchOutput(
            query=input_data.query_text,
            matches=final_matches,
            cases_retrieved_count=len(candidates),
            cases_verified_count=len(final_matches),
            status_summary=f"Successfully retrieved and verified {len(final_matches)} precedents from database",
            confidence=round(confidence, 2),
            needs_human_review=review_needed,
            audit_notes=f"Retrieved {len(candidates)} candidates from DB; verified {len(final_matches)}.",
        )

