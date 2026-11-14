"""Tests for Case Law Retrieval, Database Verification, and Hard Rule 4."""

from app.db.models import PrecedentCaseModel
from app.retrieval.verifier import CaseLawVerifier
from app.retrieval.retriever import HybridRetriever
from app.agents.precedent import PrecedentAnalysisAgent
from app.schemas.precedent import PrecedentSearchInput
from app.llm.client import MockLLMClient


def test_hard_rule_4_invented_case_rejected(db_session):
    """Enforces Hard Rule 4: Verifier rejects any invented or hallucinated case."""
    verifier = CaseLawVerifier(db_session)
    
    # Hallucinated case ID that does NOT exist in DB
    result = verifier.verify_case_id("hallucinated-case-uuid-999")
    assert result.is_valid is False
    assert "does not exist in local verified database" in result.rejection_reason


def test_hard_rule_4_valid_db_case_verified(db_session):
    """Verify that a legitimate DB record is verified and returned."""
    # Seed a verified case
    case = PrecedentCaseModel(
        case_title="K.S. Puttaswamy v. Union of India",
        citation="(2017) 10 SCC 1",
        court="Supreme Court of India",
        judgment_date="2017-08-24",
        bench="9 Judge Constitution Bench",
        summary="Right to privacy declared a fundamental right under Article 21.",
        ratio_decidendi="Privacy is a constitutionally protected right emerging from Article 21.",
        full_text="Full text...",
    )
    db_session.add(case)
    db_session.commit()

    verifier = CaseLawVerifier(db_session)
    result = verifier.verify_case_id(str(case.id))
    assert result.is_valid is True
    assert result.case.case_title == "K.S. Puttaswamy v. Union of India"
    assert result.case.db_verified is True


def test_hard_rule_4_not_found_when_empty_db(db_session):
    """Enforces Hard Rule 4: If nothing is found in DB, return 'not found'."""
    agent = PrecedentAnalysisAgent(db_session=db_session)
    input_data = PrecedentSearchInput(
        query_text="Section 138 Negotiable Instruments Act cheque bounce notice limitation",
        top_k=3,
    )
    output = agent.run(input_data)
    assert output.status_summary == "not found"
    assert len(output.matches) == 0
    assert output.cases_verified_count == 0


def test_precedent_agent_retrieves_and_verifies_from_db(db_session):
    """Verify end-to-end agent retrieval and summarization of verified DB cases."""
    case = PrecedentCaseModel(
        case_title="Anvar P.V. v. P.K. Basheer",
        citation="(2014) 10 SCC 473",
        court="Supreme Court of India",
        judgment_date="2014-09-18",
        summary="Electronic evidence admissibility under Section 65B.",
        ratio_decidendi="Section 65B certificate is mandatory for secondary electronic evidence.",
    )
    db_session.add(case)
    db_session.commit()

    mock_llm = MockLLMClient(
        responses={
            "VERIFIED DATABASE RECORDS": {
                "summaries": [
                    {
                        "case_db_id": str(case.id),
                        "relevance_explanation": "Directly applies to WhatsApp chats lacking 65B certificate.",
                        "ratio_decidendi_snippet": "Section 65B certificate is mandatory.",
                    }
                ],
                "confidence": 0.92,
            }
        }
    )

    agent = PrecedentAnalysisAgent(db_session=db_session, llm_client=mock_llm)
    input_data = PrecedentSearchInput(
        query_text="electronic evidence email certificate",
        top_k=1,
    )
    output = agent.run(input_data)

    assert len(output.matches) == 1
    assert output.matches[0].case.case_title == "Anvar P.V. v. P.K. Basheer"
    assert output.matches[0].case.db_verified is True
    assert output.confidence >= 0.75
    assert output.needs_human_review is False

