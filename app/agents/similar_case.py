"""Similar Case Retrieval Agent adhering strictly to Hard Rule 4.

Follows Hard Rule 4:
Case law / similar-case results must come ONLY from the database via retrieval.
The LLM must NEVER generate, recall, or invent case names, citations or judgments.
LLM may only summarize text that retrieval returned, and every cited case id must be
verified to exist in DB before output. If nothing is found, return "no similar case found".

Follows Hard Rule 1: Typed Pydantic input and output, run() method, no hidden global state.
Follows Hard Rule 3: Output carries confidence and needs_human_review.
"""

import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.db.models import Judgment
from app.schemas.precedent import (
    SimilarCase,
    SimilarCaseInput,
    SimilarCaseOutput,
)
from app.schemas.facts import ExtractedFacts
from app.retrieval.hybrid import (
    HybridRetriever,
    RetrievalFilter,
    RetrievedChunk,
    Reranker,
    NoOpReranker,
)
from app.llm.client import LLMClient, Embedder

logger = logging.getLogger(__name__)


class _LLMRetrievedTextSummary(BaseModel):
    summary: str = Field(..., description="Concise legal summary strictly grounded in provided text")
    key_legal_holding: Optional[str] = None


class SimilarCaseAgent(BaseAgent[SimilarCaseInput, SimilarCaseOutput]):
    """Retrieves verified precedent cases by constructing a case fingerprint and querying HybridRetriever."""

    agent_name: str = "SimilarCaseAgent"

    def __init__(
        self,
        db_session: Session,
        llm_client: Optional[LLMClient] = None,
        embedder: Optional[Embedder] = None,
        reranker: Optional[Reranker] = None,
    ):
        super().__init__(llm_client=llm_client)
        self.session = db_session
        self.retriever = HybridRetriever(
            db_session=db_session,
            embedder=embedder,
            reranker=reranker or NoOpReranker(),
        )

    def _execute(self, input_data: SimilarCaseInput) -> SimilarCaseOutput:
        # ---------------------------------------------------------------------
        # Step 1: Build Case Fingerprint Query & Structured Filters
        # ---------------------------------------------------------------------
        fingerprint_text, structured_filter = self._build_case_fingerprint(input_data)

        if not fingerprint_text.strip():
            return SimilarCaseOutput(
                case_id=input_data.case_id,
                fingerprint_query="",
                similar_cases=[],
                total_found=0,
                message="no similar case found",
                confidence=1.0,
                needs_human_review=False,
                audit_notes="Empty case facts and query; no fingerprint could be generated.",
            )

        # ---------------------------------------------------------------------
        # Step 2: Retrieve Top-K Chunks via HybridRetriever
        # ---------------------------------------------------------------------
        retrieved_chunks = self.retriever.retrieve(
            query=fingerprint_text,
            top_k=input_data.top_k * 3,
            filters=structured_filter,
        )

        # Filter by score threshold
        valid_chunks = [c for c in retrieved_chunks if c.score >= input_data.score_threshold]

        if not valid_chunks:
            return SimilarCaseOutput(
                case_id=input_data.case_id,
                fingerprint_query=fingerprint_text,
                similar_cases=[],
                total_found=0,
                message="no similar case found",
                confidence=1.0,
                needs_human_review=False,
                audit_notes="No precedent cases exceeded similarity threshold in local database.",
            )

        # ---------------------------------------------------------------------
        # Step 3: Group Chunks by Judgment & Extract Stored Metadata
        # ---------------------------------------------------------------------
        chunks_by_judgment: Dict[str, List[RetrievedChunk]] = {}
        for c in valid_chunks:
            chunks_by_judgment.setdefault(c.judgment_id, []).append(c)

        case_sections = input_data.sections or []
        if input_data.extracted_facts:
            case_sections.extend([f"{s.act} {s.section_number}".strip() for s in input_data.extracted_facts.sections])
            case_sections.extend([s.section_number.strip() for s in input_data.extracted_facts.sections])

        candidate_cases: List[SimilarCase] = []

        for j_id, group in chunks_by_judgment.items():
            # HARD RULE 4: Look up directly from DB. NEVER invent or hallucinate.
            judgment_db = self.session.get(Judgment, j_id)
            if not judgment_db:
                continue

            matched_paras = [g.text for g in group]
            best_chunk = max(group, key=lambda x: x.score)
            agg_score = round(best_chunk.score, 4)

            # Determine why it is similar from stored metadata
            stored_sections = []
            if judgment_db.sections_cited:
                try:
                    stored_sections = json.loads(judgment_db.sections_cited)
                except Exception:
                    stored_sections = [judgment_db.sections_cited]

            # Compute sections overlap
            overlap: List[str] = []
            for cs in case_sections:
                for ss in stored_sections:
                    if cs.lower() in ss.lower() or ss.lower() in cs.lower():
                        if ss not in overlap:
                            overlap.append(ss)

            fact_overlap_desc = f"Matched factual controversy concerning {judgment_db.outcome or 'disputed claims'}."
            why_desc = (
                f"Statutory sections overlap: {', '.join(overlap) if overlap else 'Common statutory domain'}; "
                f"Procedural outcome: {judgment_db.outcome or 'Adjudicated'}."
            )
            if getattr(judgment_db, "is_overruled", False):
                overruled_cite = getattr(judgment_db, "overruled_by_citation", None)
                warning_suffix = f" [WARNING: Precedent ratio marked OVERRULED{f' by {overruled_cite}' if overruled_cite else ''}. Exercise caution.]"
                why_desc += warning_suffix

            # Optional LLM Grounded Summary
            summary_text = None
            if input_data.summarize_with_llm and matched_paras:
                summary_text = self._summarize_retrieved_text(
                    title=judgment_db.title,
                    citation=judgment_db.citation,
                    matched_text="\n\n".join(matched_paras[:2]),
                )

            similar_case = SimilarCase(
                case_id=str(judgment_db.id),
                title=judgment_db.title,
                court=judgment_db.court,
                date=judgment_db.date,
                citation=judgment_db.citation,
                url=judgment_db.source_url,
                source_url=judgment_db.source_url,
                outcome=judgment_db.outcome,
                matched_paragraph=matched_paras[0],
                matched_paragraphs=matched_paras,
                score=agg_score,
                why_similar=why_desc,
                sections_overlap=overlap,
                fact_overlap=fact_overlap_desc,
                summary=summary_text,
            )
            candidate_cases.append(similar_case)

        # Sort by similarity score descending
        candidate_cases.sort(key=lambda x: x.score, reverse=True)
        top_cases = candidate_cases[: input_data.top_k]

        # ---------------------------------------------------------------------
        # Step 4: Strict Post-Check (Hard Rule 4 Enforcement)
        # ---------------------------------------------------------------------
        verified_cases: List[SimilarCase] = []
        for c in top_cases:
            record = self.session.get(Judgment, c.case_id)
            if record and record.citation == c.citation:
                verified_cases.append(c)
            else:
                logger.error(f"HARD RULE 4 GUARD: Stripped unverified precedent {c.case_id} / {c.citation}!")

        if not verified_cases:
            return SimilarCaseOutput(
                case_id=input_data.case_id,
                fingerprint_query=fingerprint_text,
                similar_cases=[],
                total_found=0,
                message="no similar case found",
                confidence=1.0,
                needs_human_review=False,
                audit_notes="All candidate cases failed local DB verification check.",
            )

        return SimilarCaseOutput(
            case_id=input_data.case_id,
            fingerprint_query=fingerprint_text,
            similar_cases=verified_cases,
            total_found=len(verified_cases),
            message="Similar cases successfully retrieved and verified from DB",
            confidence=0.92,
            needs_human_review=False,
            audit_notes=f"Retrieved {len(verified_cases)} verified precedent cases from local database for fingerprint query.",
        )

    def _build_case_fingerprint(self, input_data: SimilarCaseInput) -> Tuple[str, RetrievalFilter]:
        """Build case fingerprint text and structured filters from extracted facts or query text."""
        parts = []
        filter_court = input_data.court
        filter_sections: List[str] = input_data.sections or []

        if input_data.extracted_facts:
            ef = input_data.extracted_facts
            # Offence / incidents
            if ef.incidents:
                parts.append(" ".join([inc.description for inc in ef.incidents[:2]]))
            # Sections
            if ef.sections:
                sec_strs = [f"{s.act} {s.section_number}".strip() for s in ef.sections]
                parts.append("Statutory sections: " + ", ".join(sec_strs))
                filter_sections.extend([s.section_number for s in ef.sections])
            # Parties
            if ef.parties:
                parts.append("Parties involved: " + ", ".join([f"{p.name} ({p.role})" for p in ef.parties[:4]]))
            # Court
            if ef.court and not filter_court:
                filter_court = ef.court
                parts.append(f"Court: {ef.court}")

        if input_data.query_text:
            parts.insert(0, input_data.query_text.strip())

        fingerprint = ". ".join(p.strip().rstrip(".") for p in parts if p.strip())

        retrieval_filter = RetrievalFilter(
            court=filter_court,
            year_range=input_data.year_range,
            sections_cited=filter_sections if filter_sections else None,
            outcome=input_data.outcome,
        )

        return fingerprint, retrieval_filter

    def _summarize_retrieved_text(self, title: str, citation: str, matched_text: str) -> str:
        """Summarize ONLY the retrieved text, strictly forbidding outside knowledge."""
        prompt = (
            f"Case Title: {title}\n"
            f"Citation: {citation}\n\n"
            f"Retrieved Verbatim Text from Database:\n\"\"\"\n{matched_text[:3000]}\n\"\"\"\n\n"
            f"Instructions:\n"
            f"Summarize ONLY the specific legal principle or ratio decidendi contained in the text above.\n"
            f"STRICT PROHIBITION: You must NOT recall, introduce, or cite any other judgments, outside facts, "
            f"or legal cases not present in the excerpt above."
        )
        system = "You are a legal research summarizer strictly bound to provided database text."

        try:
            res, _ = self.llm.generate_structured(prompt=prompt, schema=_LLMRetrievedTextSummary, system=system)
            return res.summary
        except Exception:
            return matched_text[:250] + "..."

