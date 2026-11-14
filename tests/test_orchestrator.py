"""Tests for LangGraph multi-agent orchestration pipeline."""

from app.db.models import PrecedentCaseModel
from app.orchestrator.graph import LegalOrchestrator
from app.llm.client import MockLLMClient


def test_full_langgraph_orchestration(db_session):
    """Verify end-to-end multi-agent LangGraph workflow execution."""
    # Seed DB with a precedent
    case = PrecedentCaseModel(
        case_title="Standard Chartered Bank v. Dharminder Bhohi",
        citation="(2013) 15 SCC 341",
        court="Supreme Court of India",
        judgment_date="2013-09-13",
        summary="Limitation and statutory remedies before DRT.",
        ratio_decidendi="Tribunals are bound by statutory limitation and cannot travel beyond statutory bounds.",
    )
    db_session.add(case)
    db_session.commit()

    brief_text = (
        "IN THE HIGH COURT OF DELHI AT NEW DELHI\n"
        "Petitioner: Alpha Tech Pvt Ltd\n"
        "Respondent: Beta Enterprises\n"
        "On 10-02-2022, Petitioner delivered software licenses worth Rs. 25,00,000.\n"
        "Respondent issued cheque No. 123456 which dishonoured on 15-03-2022.\n"
        "Petitioner issued statutory demand notice on 25-03-2022 by registered post.\n"
        "Respondent failed to make payment within 15 days."
    )

    mock_llm = MockLLMClient(
        responses={
            "Analyze the following legal document": {
                "detected_language": "english",
                "parties_plaintiff": ["Alpha Tech Pvt Ltd"],
                "parties_defendant": ["Beta Enterprises"],
                "court_name": "High Court of Delhi",
                "case_number": "Co. Petition 99/2023",
                "candidate_facts": [
                    {
                        "fact_id": "FACT-001",
                        "category": "CHEQUE_DISHONOUR",
                        "statement": "Respondent issued cheque No. 123456 which dishonoured on 15-03-2022",
                        "snippet": "Respondent issued cheque No. 123456 which dishonoured on 15-03-2022.",
                        "page": 1,
                    }
                ],
                "extraction_confidence": 0.90,
            },
            "statutory limitation": {
                "cause_of_action_identified": "2022-04-10 - Failure to pay within 15 days of notice",
                "events": [
                    {
                        "event_id": "EV-001",
                        "date_str": "2022-03-15",
                        "event_title": "Dishonour of Cheque",
                        "description": "Cheque returned unpaid",
                        "is_cause_of_action": False,
                        "fact_id": "FACT-001",
                    }
                ],
                "limitation_assessments": [
                    {
                        "statute": "Negotiable Instruments Act 1881",
                        "section_or_article": "Section 138(c)",
                        "prescribed_period": "30 days from expiry of notice period",
                        "is_time_barred": False,
                        "legal_basis": "Complaint filed within 1 month.",
                    }
                ],
                "has_limitation_risk": False,
                "confidence": 0.92,
            },
            "VERIFIED DATABASE RECORDS": {
                "summaries": [
                    {
                        "case_db_id": str(case.id),
                        "relevance_explanation": "Tribunal limitation applicability.",
                        "ratio_decidendi_snippet": "Tribunals are bound by statutory limitation.",
                    }
                ],
                "confidence": 0.90,
            },
            "potential legal and procedural risks": {
                "risks": [
                    {
                        "risk_id": "RISK-001",
                        "category": "STATUTORY_COMPLIANCE",
                        "severity": "LOW",
                        "statutory_provision": "Section 138 NI Act",
                        "issue_description": "Postal receipt and delivery tracking required to prove service of notice.",
                        "mitigation_strategy": "Annex India Post delivery confirmation certificate with affidavit.",
                    }
                ],
                "overall_risk_level": "LOW",
                "confidence": 0.88,
            },
        }
    )

    orchestrator = LegalOrchestrator(db_session=db_session, llm_client=mock_llm)
    report = orchestrator.analyze_document(
        document_id="doc-delhi-001",
        raw_text=brief_text,
        filename="company_petition.txt",
    )

    assert report is not None
    assert "Alpha Tech Pvt Ltd" in report.case_summary
    assert len(report.document_extraction.facts) == 1
    assert len(report.timeline_analysis.limitation_assessments) == 1
    assert len(report.precedents.matches) == 1
    assert report.precedents.matches[0].case.case_title == "Standard Chartered Bank v. Dharminder Bhohi"
    assert len(report.strategic_recommendations) >= 1
    assert "LEGAL DISCLAIMER" in report.disclaimer
    assert report.confidence >= 0.75

