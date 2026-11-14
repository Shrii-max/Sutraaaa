"""Tests for all individual Agent classes and Hard Rules 1, 2, 3, 5, 7."""

from app.schemas.facts import DocumentExtractionInput
from app.schemas.timeline import TimelineAnalysisInput
from app.schemas.risks import RiskAnalysisInput
from app.schemas.source import SourceReference
from app.schemas.facts import FactItem
from app.agents.fact_extraction import FactExtractionAgent
from app.agents.timeline import LimitationTimelineAgent
from app.agents.legal_risk import LegalRiskAgent
from app.llm.client import MockLLMClient
from app.security.audit import AuditLogger


def test_fact_extraction_agent_with_provenance_and_rejection():
    """Verify FactExtractionAgent extracts facts with SourceReference and rejects unsourced facts."""
    doc_text = (
        "IN THE COURT OF SENIOR CIVIL JUDGE, SAKET, NEW DELHI\n"
        "Suit No. 450 of 2023\n"
        "Ramesh Kumar (Plaintiff) v. Suresh Sharma (Defendant)\n"
        "1. On 10-01-2022, Plaintiff advanced a loan of Rs. 5,00,000 to Defendant.\n"
        "2. Defendant issued a promissory note agreeing to repay within one year.\n"
        "3. Defendant failed to repay on due date 10-01-2023."
    )

    # Candidate 1 has valid snippet, Candidate 2 has NO snippet/offsets (must be rejected)
    mock_llm = MockLLMClient(
        responses={
            "Analyze the following legal document": {
                "detected_language": "english",
                "parties_plaintiff": ["Ramesh Kumar"],
                "parties_defendant": ["Suresh Sharma"],
                "court_name": "Court of Senior Civil Judge, Saket, New Delhi",
                "case_number": "Suit No. 450 of 2023",
                "candidate_facts": [
                    {
                        "fact_id": "FACT-001",
                        "category": "TRANSACTION",
                        "statement": "Plaintiff advanced loan of Rs. 5,00,000",
                        "snippet": "Plaintiff advanced a loan of Rs. 5,00,000 to Defendant.",
                        "page": 1,
                    },
                    {
                        "fact_id": "FACT-002",
                        "category": "UNSOURCED_CLAIM",
                        "statement": "Defendant also stole jewellery",
                        "snippet": None,  # Missing snippet -> REJECTED
                        "page": None,
                    },
                ],
                "extraction_confidence": 0.88,
            }
        }
    )

    agent = FactExtractionAgent(llm_client=mock_llm)
    input_data = DocumentExtractionInput(
        document_id="doc-saket-001",
        filename="plaint.txt",
        text_content=doc_text,
    )
    output = agent.run(input_data)

    # Verify Hard Rule 2: Unsourced fact rejected, valid fact accepted with SourceReference
    assert len(output.facts) == 1
    assert output.rejected_facts_count == 1
    assert output.facts[0].fact_id == "FACT-001"
    assert isinstance(output.facts[0].source, SourceReference)
    assert output.facts[0].source.document_id == "doc-saket-001"
    assert output.facts[0].source.char_end > output.facts[0].source.char_start

    # Verify Hard Rule 3 & 10: Confidence and Disclaimer
    assert 0.0 <= output.confidence <= 1.0
    assert "LEGAL DISCLAIMER" in output.disclaimer


def test_limitation_timeline_agent():
    """Verify LimitationTimelineAgent assesses limitation under Indian law."""
    src = SourceReference(
        document_id="doc-001",
        page=1,
        char_start=0,
        char_end=50,
        snippet="Defendant failed to pay invoice due on 15-05-2021",
    )
    facts = [
        FactItem(
            fact_id="FACT-001",
            category="BREACH",
            statement="Defendant breached contract by refusing payment on 15-05-2021",
            date_mentioned="2021-05-15",
            source=src,
        )
    ]

    mock_llm = MockLLMClient(
        responses={
            "statutory limitation": {
                "cause_of_action_identified": "2021-05-15 - Default in invoice payment",
                "events": [
                    {
                        "event_id": "EV-001",
                        "date_str": "2021-05-15",
                        "event_title": "Default in Payment",
                        "description": "Invoice defaulted",
                        "is_cause_of_action": True,
                        "fact_id": "FACT-001",
                    }
                ],
                "limitation_assessments": [
                    {
                        "statute": "Limitation Act 1963",
                        "section_or_article": "Article 55 - Breach of Contract",
                        "prescribed_period": "3 years",
                        "cause_of_action_date": "2021-05-15",
                        "limitation_expiry_date": "2024-05-15",
                        "is_time_barred": False,
                        "delay_condonation_applicable": True,
                        "legal_basis": "3 years from date of contract breach under Article 55.",
                    }
                ],
                "has_limitation_risk": False,
                "confidence": 0.89,
            }
        }
    )

    agent = LimitationTimelineAgent(llm_client=mock_llm)
    input_data = TimelineAnalysisInput(document_id="doc-001", facts=facts)
    output = agent.run(input_data)

    assert len(output.events_chronological) == 1
    assert output.events_chronological[0].is_cause_of_action is True
    assert len(output.limitation_assessments) == 1
    assert output.limitation_assessments[0].prescribed_period == "3 years"
    assert output.has_limitation_risk is False


def test_legal_risk_agent_electronic_evidence_and_cpc():
    """Verify LegalRiskAgent identifies Section 65B/63 electronic certificate and procedural risks."""
    src = SourceReference(
        document_id="doc-002",
        page=1,
        char_start=0,
        char_end=40,
        snippet="Plaintiff sent WhatsApp message confirming payment",
    )
    facts = [
        FactItem(
            fact_id="FACT-001",
            category="EVIDENCE",
            statement="Plaintiff relied on WhatsApp chats and email printouts",
            source=src,
        )
    ]

    mock_llm = MockLLMClient(
        responses={
            "potential legal and procedural risks": {
                "risks": [
                    {
                        "risk_id": "RISK-001",
                        "category": "PROCEDURAL_DEFECT",
                        "severity": "MEDIUM",
                        "statutory_provision": "Order VII Rule 11 CPC",
                        "issue_description": "Plaint may face maintainability challenge if valuation incorrect.",
                        "mitigation_strategy": "Verify court fee calculation as per Court Fees Act.",
                    }
                ],
                "overall_risk_level": "MEDIUM",
                "confidence": 0.85,
            }
        }
    )

    agent = LegalRiskAgent(llm_client=mock_llm)
    input_data = RiskAnalysisInput(document_id="doc-002", facts=facts)
    output = agent.run(input_data)

    # Should detect both CPC Order VII Rule 11 and Section 65B/63 electronic evidence
    assert len(output.risks) >= 2
    provisions = [r.statutory_provision for r in output.risks]
    assert any("65B" in p or "63" in p for p in provisions)
    assert any("Order VII Rule 11" in p for p in provisions)


def test_hard_rule_5_audit_log_written_for_all_agent_runs():
    """Enforces Hard Rule 5: Every agent run writes an append-only audit log row."""
    initial_count = len(AuditLogger.get_records())

    mock_llm = MockLLMClient()
    agent = FactExtractionAgent(llm_client=mock_llm)
    agent.run(DocumentExtractionInput(document_id="audit-test-doc", filename="test.txt", text_content="Sample text"))

    final_count = len(AuditLogger.get_records())
    assert final_count > initial_count
    last_record = AuditLogger.get_records()[-1]
    assert last_record.event_type == "AGENT_RUN"
    assert "FactExtractionAgent" in last_record.actor

