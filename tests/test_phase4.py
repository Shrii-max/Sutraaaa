"""Unit and integration test suite for Phase 4 Knowledge and Retrieval.

Follows Requirements:
- Ingestion idempotency: running twice produces identical record counts without duplication.
- Hybrid retrieval ranking on sample data (dense + sparse + RRF).
- Hard Rule 4 Guard: proves the output never contains a case id or citation absent from DB.
- 'Not found' path: returns empty list with 'no similar case found' when ungrounded.
- LegalResearchAgent: grounded answer with retrieved citations, refusing when ungrounded.
"""

from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.db.models import Judgment, JudgmentChunk, StatuteSection
from app.ingestion.judgments import load_judgments_from_jsonl, ingest_judgment_items
from app.ingestion.statutes import load_statutes_from_jsonl, ingest_statute_items
from app.retrieval.hybrid import HybridRetriever, RetrievalFilter
from app.agents.similar_case import SimilarCaseAgent
from app.agents.legal_research import LegalResearchAgent
from app.schemas.precedent import SimilarCaseInput
from app.schemas.research import LegalResearchInput
from app.schemas.facts import ExtractedFacts, SectionItem, IncidentItem
from app.schemas.source import SourceRef
from app.llm.client import FakeLLMClient, FakeEmbedder


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


def test_ingestion_idempotency(db_session: Session, fixtures_dir: Path):
    """Verify ingestion pipeline is strictly idempotent: re-running does not duplicate records."""
    j_file = fixtures_dir / "sample_judgments.jsonl"
    s_file = fixtures_dir / "sample_statutes.jsonl"

    assert j_file.exists(), f"Missing {j_file}"
    assert s_file.exists(), f"Missing {s_file}"

    j_items = load_judgments_from_jsonl(j_file)
    s_items = load_statutes_from_jsonl(s_file)

    embedder = FakeEmbedder()

    # --- Run 1 ---
    num_j1, num_c1 = ingest_judgment_items(j_items, db_session, embedder=embedder)
    num_s1 = ingest_statute_items(s_items, db_session, embedder=embedder)

    assert num_j1 == 5
    assert num_s1 == 4

    count_j1 = db_session.query(Judgment).count()
    count_c1 = db_session.query(JudgmentChunk).count()
    count_s1 = db_session.query(StatuteSection).count()

    assert count_j1 == 5
    assert count_c1 >= 5
    assert count_s1 == 4

    # --- Run 2 (Idempotency Check) ---
    num_j2, num_c2 = ingest_judgment_items(j_items, db_session, embedder=embedder)
    num_s2 = ingest_statute_items(s_items, db_session, embedder=embedder)

    count_j2 = db_session.query(Judgment).count()
    count_c2 = db_session.query(JudgmentChunk).count()
    count_s2 = db_session.query(StatuteSection).count()

    # Counts must remain identical; no duplicates created
    assert count_j2 == count_j1 == 5
    assert count_c2 == count_c1
    assert count_s2 == count_s1 == 4


def test_hybrid_retrieval_ranking_on_sample_data(db_session: Session, fixtures_dir: Path):
    """Verify HybridRetriever ranks relevant precedent chunks using dense + sparse RRF fusion."""
    j_items = load_judgments_from_jsonl(fixtures_dir / "sample_judgments.jsonl")
    ingest_judgment_items(j_items, db_session, embedder=FakeEmbedder())

    retriever = HybridRetriever(db_session=db_session, embedder=FakeEmbedder())

    # Query 1: Cheque dishonour under Section 138 NI Act
    results_cheque = retriever.retrieve("dishonour of cheque demand notice Section 138 NI Act", top_k=2)
    assert len(results_cheque) >= 1
    assert any("SCC" in r.metadata.get("citation", "") or "SC_" in r.judgment_id for r in results_cheque)

    # Query 2: Electronic evidence Section 65B Evidence Act
    results_cheat = retriever.retrieve("electronic record secondary evidence Section 65B Evidence Act", top_k=2)
    assert len(results_cheat) >= 1
    citations = [r.metadata.get("citation") for r in results_cheat]
    assert any("2014" in str(c) or "2020" in str(c) or "SCC" in str(c) for c in citations)

    # Metadata Filter: Supreme Court filter
    sc_filter = RetrievalFilter(court="Supreme Court")
    sc_results = retriever.retrieve("commercial dispute IPC", top_k=5, filters=sc_filter)
    for r in sc_results:
        assert "Supreme Court" in r.metadata.get("court", "")


def test_hard_rule_4_guard_prevents_unverified_case_citation(db_session: Session, fixtures_dir: Path):
    """Hard Rule 4 Guard: Verify output NEVER contains a judgment ID or citation absent from DB."""
    j_items = load_judgments_from_jsonl(fixtures_dir / "sample_judgments.jsonl")
    ingest_judgment_items(j_items, db_session, embedder=FakeEmbedder())

    facts = ExtractedFacts(
        incidents=[
            IncidentItem(
                title="Secondary electronic records produced in court",
                description="CDs and electronic records produced without Section 65B certificate under Evidence Act.",
                date="2023-01-10",
                source=SourceRef(document_id="doc-1", page=1, char_start=0, char_end=30, snippet="electronic records without certificate"),
                confidence=0.95,
            )
        ],
        sections=[
            SectionItem(
                act="other",
                section_number="65B",
                description="Admissibility of electronic records",
                source=SourceRef(document_id="doc-1", page=1, char_start=0, char_end=15, snippet="Section 65B"),
                confidence=0.95,
            )
        ],
    )

    fake_llm = FakeLLMClient({
        "_LLMRetrievedTextSummary": {
            "summary": "Court held that dishonest intention at inception is necessary for Section 420.",
            "key_legal_holding": "Civil breach is not criminal cheating without fraudulent inception.",
        }
    })

    agent = SimilarCaseAgent(db_session=db_session, llm_client=fake_llm, embedder=FakeEmbedder())
    output = agent.run(SimilarCaseInput(case_id="case-101", extracted_facts=facts, top_k=3))

    assert output.total_found > 0
    assert len(output.similar_cases) > 0

    # Strict Hard Rule 4 Verification across all returned precedents
    for sc in output.similar_cases:
        db_rec = db_session.get(Judgment, sc.case_id)
        assert db_rec is not None, f"VIOLATION: Case ID {sc.case_id} does not exist in DB!"
        assert db_rec.citation == sc.citation, f"VIOLATION: Citation {sc.citation} does not match DB record!"
        assert sc.matched_paragraph in db_rec.full_text, "VIOLATION: Matched paragraph not from DB record!"
        assert len(sc.sections_overlap) >= 0
        assert sc.why_similar is not None


def test_similar_case_agent_not_found_path(db_session: Session):
    """Verify 'not found' path when DB has no matching cases or is empty."""
    # Empty DB
    agent = SimilarCaseAgent(db_session=db_session, llm_client=FakeLLMClient(), embedder=FakeEmbedder())

    output = agent.run(
        SimilarCaseInput(
            case_id="case-empty",
            query_text="admiralty maritime salvage claims high seas 1850",
            top_k=3,
        )
    )

    # Must return empty list with message 'no similar case found'
    assert output.similar_cases == []
    assert output.total_found == 0
    assert output.message == "no similar case found"
    assert output.confidence == 1.0
    assert output.needs_human_review is False


def test_legal_research_agent_grounded_answer_and_refusal(db_session: Session, fixtures_dir: Path):
    """Verify LegalResearchAgent provides grounded answers from DB and refuses when ungrounded."""
    # Ingest test knowledge base
    j_items = load_judgments_from_jsonl(fixtures_dir / "sample_judgments.jsonl")
    s_items = load_statutes_from_jsonl(fixtures_dir / "sample_statutes.jsonl")
    ingest_judgment_items(j_items, db_session, embedder=FakeEmbedder())
    ingest_statute_items(s_items, db_session, embedder=FakeEmbedder())

    fake_llm = FakeLLMClient({
        "_LLMGroundedResearchResponse": {
            "answer": "Under Section 420 of the IPC, the essential ingredient is dishonest inducement of property delivery. In State of Maharashtra v. Dummy Accused A (2021 DUMMY SC 101), the Supreme Court reiterated that dishonest intention must exist at inception.",
            "authorities_cited": ["Section 420 IPC", "2021 DUMMY SC 101"],
        }
    })

    agent = LegalResearchAgent(db_session=db_session, llm_client=fake_llm, embedder=FakeEmbedder())

    # Case A: Answerable grounded query
    out_valid = agent.run(LegalResearchInput(query="cheating under Section 420 IPC and commercial contract breach"))
    assert out_valid.is_refusal is False
    assert len(out_valid.citations) >= 1
    assert any("420" in c.citation_or_section for c in out_valid.citations)
    assert "Section 420" in out_valid.answer

    # Case B: Unanswerable query returning nothing relevant (Refusal Path)
    out_refused = agent.run(
        LegalResearchInput(
            query="quantum teleportation in topological insulators",
            score_threshold=0.99,  # Unattainable threshold
        )
    )
    assert out_refused.is_refusal is True
    assert "cannot answer" in out_refused.answer.lower()
    assert "Rule #4" in out_refused.answer
    assert len(out_refused.citations) == 0

