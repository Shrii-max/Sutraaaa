"""Legal Research Agent over Indian judgments and bare-act statutes.

Follows Requirement:
4. LegalResearchAgent: free-text query to retrieval over judgments + statutes, grounded
   answer with citations to retrieved chunks only. Answer must refuse if retrieval
   returns nothing relevant.

Follows Hard Rule 4: Zero hallucinated citations or authorities.
Follows Hard Rule 1: Typed Pydantic input/output, run() method, no hidden global state.
Follows Hard Rule 3: Output carries confidence and needs_human_review.
"""

import json
import logging
import math
import re
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.agents.base import BaseAgent
from app.db.models import Judgment, JudgmentChunk, StatuteSection
from app.schemas.research import (
    ResearchCitation,
    LegalResearchInput,
    LegalResearchOutput,
)
from app.retrieval.constitution import lookup_articles
from app.retrieval.hybrid import HybridRetriever, RetrievalFilter, RetrievedChunk
from app.llm.client import LLMClient, Embedder, LocalEmbeddingClient

logger = logging.getLogger(__name__)


def _cosine_sim(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class _LLMGroundedResearchResponse(BaseModel):
    answer: str = Field(..., description="Legal explanation grounded strictly in the provided excerpts")
    authorities_cited: List[str] = Field(default_factory=list, description="Citations or sections explicitly used in the answer")


class LegalResearchAgent(BaseAgent[LegalResearchInput, LegalResearchOutput]):
    """Answers legal queries with strictly grounded citations across judgments and statutes, refusing when ungrounded."""

    agent_name: str = "LegalResearchAgent"

    def __init__(
        self,
        db_session: Session,
        llm_client: Optional[LLMClient] = None,
        embedder: Optional[Embedder] = None,
    ):
        super().__init__(llm_client=llm_client)
        self.session = db_session
        self.embedder = embedder or LocalEmbeddingClient()
        self.hybrid_retriever = HybridRetriever(db_session=db_session, embedder=self.embedder)

    def _execute(self, input_data: LegalResearchInput) -> LegalResearchOutput:
        query = input_data.query.strip()
        citations: List[ResearchCitation] = []

        act_filter = (input_data.act_filter or "").strip().casefold()
        if input_data.include_statutes and (not act_filter or "constitution" in act_filter):
            constitution = lookup_articles(query, input_data.top_k)
            if constitution:
                return LegalResearchOutput(
                    query=query,
                    answer="\n\n".join(
                        f"{item.citation_or_section} (PDF page {item.pdf_page})\n"
                        f"{item.verbatim_snippet}" for item in constitution
                    ),
                    citations=constitution,
                    confidence=1.0,
                    needs_human_review=False,
                    audit_notes="Returned matching text from the local Constitution archive.",
                )


        # ---------------------------------------------------------------------
        # 1. Retrieve Judgment Chunks
        # ---------------------------------------------------------------------
        if input_data.include_judgments:
            j_filter = RetrievalFilter(court=input_data.court_filter)
            j_chunks = self.hybrid_retriever.retrieve(
                query=query,
                top_k=input_data.top_k,
                filters=j_filter,
            )
            for c in j_chunks:
                clamped_score = max(0.0, min(1.0, round(c.score, 4)))
                if clamped_score >= input_data.score_threshold:
                    citations.append(
                        ResearchCitation(
                            source_type="judgment",
                            id=c.chunk_id,
                            title_or_act=c.metadata.get("title") or "Precedent Judgment",
                            citation_or_section=c.metadata.get("citation") or "Judicial Precedent",
                            verbatim_snippet=c.text,
                            score=clamped_score,
                        )
                    )

        # ---------------------------------------------------------------------
        # 2. Retrieve Bare-Act Statutes
        # ---------------------------------------------------------------------
        if input_data.include_statutes:
            statute_citations = self._retrieve_statutes(query, input_data.top_k, input_data.act_filter)
            for sc in statute_citations:
                if sc.score >= input_data.score_threshold:
                    citations.append(sc)

        # ---------------------------------------------------------------------
        # 3. Refusal Path: If Retrieval Returns Nothing Relevant
        # ---------------------------------------------------------------------
        if not citations:
            refusal_text = (
                f"I cannot answer the query '{query}' because no relevant statutory provisions or judicial "
                f"precedents were found in the local database. In strict adherence to Rule #4, I am prohibited "
                f"from generating or recalling legal assertions without verified database retrieval."
            )
            logger.info("AGENT_EXECUTION agent=LegalResearchAgent engine=rules llm_called=False fallback_taken=False")
            return LegalResearchOutput(
                query=query,
                answer=refusal_text,
                citations=[],
                is_refusal=True,
                refusal_reason="No relevant legal authorities found in the local verified database.",
                confidence=1.0,
                needs_human_review=False,
                engine="rules",
                llm_called=False,
                fallback_taken=False,
                status="rule_based",
                audit_notes="Refused query: 0 relevant citations found in database.",
            )

        # Sort all citations by relevance score
        citations.sort(key=lambda x: x.score, reverse=True)
        top_citations = citations[: input_data.top_k]

        # ---------------------------------------------------------------------
        # 4. Synthesize Grounded Answer with LLM
        # ---------------------------------------------------------------------
        passages_block = "\n\n".join([
            f"--- [{idx + 1}] Source: {c.source_type.upper()} | {c.title_or_act} ({c.citation_or_section}) ---\n"
            f"Verbatim Text: \"\"\"{c.verbatim_snippet}\"\"\""
            for idx, c in enumerate(top_citations)
        ])

        prompt = (
            f"Legal Research Query:\n\"{query}\"\n\n"
            f"VERIFIED AUTHORITATIVE PASSAGES FROM LOCAL DATABASE:\n"
            f"{passages_block}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Formulate a comprehensive, grounded answer addressing the user's legal question.\n"
            f"2. Your answer MUST be based SOLELY and EXCLUSIVELY on the verified passages provided above.\n"
            f"3. Cite the exact statutory section or case citation whenever asserting a rule.\n"
            f"4. STRICT PROHIBITION: You must NEVER invent, recall, or introduce any outside cases, statutes, "
            f"or legal principles not present in the excerpts above."
        )

        system = (
            "You are a Senior Legal Research Counsel in India. You answer questions strictly and solely "
            "from the verified judicial and statutory excerpts provided. Outside recall is strictly forbidden."
        )

        llm_called = False
        fallback_taken = True
        try:
            res, review_needed = self.llm.generate_structured(
                prompt=prompt,
                schema=_LLMGroundedResearchResponse,
                system=system,
            )
            if not review_needed and res and getattr(res, "answer", None):
                final_answer = res.answer
                llm_called = True
                fallback_taken = False
            else:
                raise RuntimeError("LLM response ungrounded or empty")
        except Exception:
            # Deterministic fallback answer quoting top authorities directly
            final_answer = (
                f"Based on the retrieved statutory and judicial authorities from the database:\n\n"
                + "\n\n".join([f"- **{c.title_or_act} ({c.citation_or_section})**: {c.verbatim_snippet[:250]}..." for c in top_citations[:3]])
            )
            llm_called = False
            fallback_taken = True

        engine_used = "llm" if llm_called else "rules"
        status_val = "live_model" if llm_called else "rule_based"
        err_msg = "Language model unreachable: response generated directly from retrieved statutory/judicial quotes." if fallback_taken else None

        logger.info(
            "AGENT_EXECUTION agent=LegalResearchAgent engine=%s llm_called=%s fallback_taken=%s",
            engine_used,
            llm_called,
            fallback_taken,
        )

        return LegalResearchOutput(
            query=query,
            answer=final_answer,
            citations=top_citations,
            is_refusal=False,
            confidence=0.92,
            needs_human_review=fallback_taken,
            engine=engine_used,
            llm_called=llm_called,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
            audit_notes=f"LegalResearchAgent synthesized grounded answer using {len(top_citations)} verified citations.",
        )

    def _retrieve_statutes(
        self, query: str, limit: int, act_filter: Optional[str]
    ) -> List[ResearchCitation]:
        """Dense and lexical search over bare-act statutory provisions."""
        stmt = select(StatuteSection)
        if act_filter:
            stmt = stmt.where(StatuteSection.act.ilike(f"%{act_filter}%"))

        statutes = self.session.execute(stmt).scalars().all()
        if not statutes:
            return []

        try:
            query_vec = self.embedder.embed_query(query)
        except Exception:
            query_vec = []
        q_terms = set(re.findall(r"\w{3,}", query.lower()))

        scored: List[Tuple[float, StatuteSection]] = []
        for s in statutes:
            emb = s.embedding
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = []
            vec_sim = _cosine_sim(query_vec, emb) if emb else 0.0

            text_comb = f"{s.act} {s.section_no} {s.heading} {s.text}".lower()
            keyword_score = sum(1 for t in q_terms if t in text_comb) / max(1, len(q_terms))

            # Hybrid score
            comb_score = (0.7 * vec_sim) + (0.3 * keyword_score)
            scored.append((comb_score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, s in scored[:limit]:
            clamped = max(0.0, min(1.0, round(score, 4)))
            results.append(
                ResearchCitation(
                    source_type="statute",
                    id=str(s.id),
                    title_or_act=s.act,
                    citation_or_section=f"Section {s.section_no}",
                    verbatim_snippet=f"Section {s.section_no} - {s.heading}: {s.text}",
                    score=clamped,
                )
            )
        return results
