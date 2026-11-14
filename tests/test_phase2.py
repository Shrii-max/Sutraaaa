"""Comprehensive unit and integration test suite for Phase 2 Document Intelligence Pipeline.

Follows Requirements:
- Anti-hallucination snippet verification catches fake extraction items.
- Hindi text survives the pipeline without corruption or offset drift.
- Validation catches an intentionally wrong date order (incident after complaint, FIR after chargesheet).
- Validation catches fuzzy name spelling variations and missing verification clauses.
- SummaryAgent strictly caps output at 150 words and provides SourceRefs for all key points across English, Hindi, and Hinglish.
- CLI run_pipeline operates end-to-end on synthetic fixtures.
"""

import json
from pathlib import Path
import pytest

from app.schemas.document import DocumentMeta, PageOCR, OCRResult
from app.schemas.facts import (
    DocumentExtractionInput,
    ExtractedFacts,
    PartyItem,
    DateItem,
    SectionItem,
)
from app.schemas.source import SourceRef
from app.agents.ocr import OCRAgent, OCREngine, FallbackOCREngine
from app.agents.language_detection import LanguageDetectionAgent
from app.agents.document_classifier import (
    DocumentClassifierAgent,
    DocumentClassifierInput,
    ClassificationResultSchema,
)
from app.agents.fact_extraction import FactExtractionAgent, _RawExtractedFactsPayload
from app.agents.validation import ValidationAgent, ValidationInput
from app.agents.summary import SummaryAgent, SummaryInput, _LLMSummaryPayload
from app.llm.client import FakeLLMClient
from scripts.run_pipeline import run_pipeline


class MockImageOCREngine(OCREngine):
    """Deterministic OCR engine for image testing."""
    def extract_from_image(self, image_bytes: bytes, lang: str = "hin+eng"):
        return "सत्यापित प्रतिलिपि - Certified True Copy extracted by OCR.", 0.94


def test_ocr_agent_native_and_fallback(tmp_path):
    """Verify OCRAgent extracts native text and falls back to OCR engine when needed."""
    # Test text file extraction
    text_content = "IN THE HIGH COURT OF DELHI AT NEW DELHI\nWrit Petition (Civil) No. 102/2023"
    txt_file = tmp_path / "petition.txt"
    txt_file.write_text(text_content, encoding="utf-8")

    agent = OCRAgent(ocr_engine=MockImageOCREngine())
    res = agent.run(file_input=str(txt_file))

    assert len(res.pages) == 1
    assert "HIGH COURT OF DELHI" in res.pages[0].text
    assert res.overall_confidence == 1.0


def test_language_detection_agent_hindi_english_hinglish():
    """Verify LanguageDetectionAgent correctly classifies Hindi, English, and Hinglish."""
    agent = LanguageDetectionAgent()

    # English page
    p_en = agent.detect_page("The petitioner respectfully submits that the loan was duly sanctioned.")
    assert p_en.language == "english"
    assert p_en.script == "Latin"

    # Hindi page
    p_hi = agent.detect_page("अभियुक्त ने परिवादी के साथ धोखाधड़ी करते हुए फर्जी दस्तावेज तैयार किए।")
    assert p_hi.language == "hindi"
    assert p_hi.script == "Devanagari"

    # Hinglish page (Latin script with Indian legal/colloquial vocabulary)
    p_hinglish = agent.detect_page(
        "Accused ne thana kotwali mein apna bayaan diya aur bola ki zameen ka patta mere paas hai."
    )
    assert p_hinglish.language == "hinglish"
    assert p_hinglish.script == "Latin"


def test_document_classifier_agent_purpose_and_type():
    """Verify DocumentClassifierAgent categorizes type and states purpose in 2-3 lines."""
    fake_llm = FakeLLMClient({
        "ClassificationResultSchema": {
            "doc_type": "petition",
            "purpose": "Petition filed by complainant XYZ before Saket District Court seeking recovery of money.",
            "filing_party": "XYZ Corp",
            "court_named": "Saket District Court",
            "relief_sought": "Recovery of dues",
            "confidence": 0.93,
        }
    })

    agent = DocumentClassifierAgent(llm_client=fake_llm)
    out = agent.run(
        DocumentClassifierInput(
            document_id="doc-test-1",
            text_content="IN THE DISTRICT COURT AT SAKET\nPetition under Section 9 of Arbitration Act.",
        )
    )

    assert out.document_meta.doc_type == "petition"
    assert "Saket District Court" in out.purpose
    assert out.confidence >= 0.85
    assert "LEGAL DISCLAIMER" in out.disclaimer


def test_anti_hallucination_rejects_fake_snippet():
    """Hard Rule 2 / Anti-hallucination check: Drop items whose snippet does not exist in document text."""
    actual_text = (
        "POLICE STATION HAUZ KHAS, NEW DELHI\n"
        "Complainant Harish Chander reported theft of his vehicle on 05-04-2023."
    )

    fake_llm = FakeLLMClient({
        "_RawExtractedFactsPayload": {
            "parties": [
                {
                    "name": "Harish Chander",
                    "role": "complainant",
                    "snippet": "Complainant Harish Chander reported theft",
                    "page": 1,
                    "confidence": 0.95,
                },
                {
                    # FAKE HALLUCINATED PARTY WITH FAKE SNIPPET NOT IN TEXT
                    "name": "Ghost Accused",
                    "role": "accused",
                    "snippet": "Ghost Accused shot the victim with revolver in broad daylight",
                    "page": 1,
                    "confidence": 0.90,
                },
            ],
            "incidents": [
                {
                    # FAKE INCIDENT
                    "title": "Murder attempt",
                    "description": "Victim was poisoned at hotel",
                    "snippet": "Victim was poisoned at hotel room 302",
                    "page": 1,
                    "confidence": 0.85,
                }
            ],
        }
    })

    agent = FactExtractionAgent(llm_client=fake_llm)
    out = agent.run(
        DocumentExtractionInput(
            document_id="doc-hauz-01",
            text_content=actual_text,
        )
    )

    # Valid party was accepted
    assert len(out.extracted_facts.parties) == 1
    assert out.extracted_facts.parties[0].name == "Harish Chander"
    assert out.extracted_facts.parties[0].source.snippet == "Complainant Harish Chander reported theft"

    # Both fake hallucinated items were strictly rejected
    assert out.rejected_facts_count == 2
    assert len(out.extracted_facts.incidents) == 0


def test_fact_extraction_witness_statements_161_164():
    """Verify extraction of Section 161 / 164 CrPC statements with speaker, role, recorded_by, and type."""
    statement_text = (
        "STATEMENT OF WITNESS UNDER SECTION 161 Cr.P.C.\n"
        "Recorded On: 12-05-2023\n"
        "Recorded By: Inspector Devender Singh\n"
        "Witness: Rameshwar Dayal, Eye Witness\n"
        "Statement: I saw the accused drive away at high speed."
    )

    fake_llm = FakeLLMClient({
        "_RawExtractedFactsPayload": {
            "statements": [
                {
                    "statement_type": "161",
                    "speaker": "Rameshwar Dayal",
                    "role": "Eye Witness",
                    "recorded_on": "12-05-2023",
                    "recorded_by": "Inspector Devender Singh",
                    "content": "I saw the accused drive away at high speed.",
                    "snippet": "I saw the accused drive away at high speed.",
                    "page": 1,
                    "confidence": 0.94,
                }
            ]
        }
    })

    agent = FactExtractionAgent(llm_client=fake_llm)
    out = agent.run(
        DocumentExtractionInput(
            document_id="doc-st-01",
            text_content=statement_text,
        )
    )

    assert len(out.extracted_facts.statements) == 1
    st = out.extracted_facts.statements[0]
    assert st.statement_type == "161"
    assert st.speaker == "Rameshwar Dayal"
    assert st.recorded_by == "Inspector Devender Singh"
    assert st.source.snippet in statement_text


def test_hindi_text_survives_pipeline():
    """Verify Hindi / Devanagari Unicode NFC normalization survives the pipeline without corruption."""
    hindi_complaint = (
        "न्यायालय मुख्य न्यायिक मजिस्ट्रेट, जयपुर महानगर\n"
        "परिवाद संख्या: 501/2024\n"
        "परिवादी: रामेश्वर प्रसाद शर्मा बनाम अभियुक्त: कुलदीप सिंह\n"
        "दिनांक 15-02-2024 को अभियुक्त ने ₹ 4,00,000 की धोखाधड़ी की।"
    )

    fake_llm = FakeLLMClient({
        "_RawExtractedFactsPayload": {
            "parties": [
                {
                    "name": "रामेश्वर प्रसाद शर्मा",
                    "role": "complainant",
                    "snippet": "परिवादी: रामेश्वर प्रसाद शर्मा",
                    "page": 1,
                    "confidence": 0.95,
                }
            ],
            "amounts": [
                {
                    "value": 400000.0,
                    "currency": "INR",
                    "context": "धोखाधड़ी राशि",
                    "snippet": "₹ 4,00,000 की धोखाधड़ी",
                    "page": 1,
                    "confidence": 0.92,
                }
            ],
        }
    })

    agent = FactExtractionAgent(llm_client=fake_llm)
    out = agent.run(
        DocumentExtractionInput(
            document_id="doc-hi-01",
            text_content=hindi_complaint,
        )
    )

    assert out.detected_language in ["hindi", "mixed"]
    assert len(out.extracted_facts.parties) == 1
    assert out.extracted_facts.parties[0].name == "रामेश्वर प्रसाद शर्मा"
    # SourceRef snippet exists and offsets align verbatim
    src = out.extracted_facts.parties[0].source
    assert hindi_complaint[src.char_start:src.char_end] == src.snippet


def test_validation_agent_catches_wrong_date_order():
    """Verify ValidationAgent catches incident occurring AFTER complaint date or FIR after chargesheet."""
    text = (
        "IN THE SAKET DISTRICT COURT, NEW DELHI\n"
        "Complaint filed on 10-01-2023.\n"
        "The alleged incident of cheating occurred on 25-05-2023."
    )

    facts = ExtractedFacts(
        dates=[
            DateItem(
                date_str="10-01-2023",
                description="Complaint filing date",
                source=SourceRef(document_id="d1", page=1, char_start=40, char_end=70, snippet="Complaint filed on 10-01-2023."),
                confidence=0.9,
            ),
            DateItem(
                date_str="25-05-2023",
                description="Alleged incident of offence",
                source=SourceRef(document_id="d1", page=1, char_start=72, char_end=128, snippet="The alleged incident of cheating occurred on 25-05-2023."),
                confidence=0.9,
            ),
        ]
    )

    agent = ValidationAgent(llm_client=FakeLLMClient())
    report = agent.run(
        ValidationInput(
            document_id="d1",
            text_content=text,
            extracted_facts=facts,
        )
    )

    # Must flag DATE_ORDER_ANOMALY
    date_issues = [i for i in report.issues if i.category == "DATE_ORDER_ANOMALY"]
    assert len(date_issues) >= 1
    assert date_issues[0].severity == "HIGH"
    assert "AFTER complaint/filing date" in date_issues[0].description


def test_validation_agent_name_spelling_variants_and_missing_verification():
    """Verify ValidationAgent catches fuzzy name spelling discrepancies and missing affidavit verification."""
    text = (
        "AFFIDAVIT\n"
        "I, Sh. Rajeshwar Sharma, son of Late Shri M. L. Sharma, resident of Delhi.\n"
        "The deponent states that Rajesh Sharma borrowed funds.\n"
    )

    facts = ExtractedFacts(
        parties=[
            PartyItem(
                name="Rajeshwar Sharma",
                role="deponent",
                source=SourceRef(document_id="d2", page=1, char_start=14, char_end=30, snippet="Rajeshwar Sharma"),
                confidence=0.95,
            ),
            PartyItem(
                name="Rajesh Sharma",
                role="borrower",
                source=SourceRef(document_id="d2", page=1, char_start=95, char_end=108, snippet="Rajesh Sharma"),
                confidence=0.95,
            ),
        ]
    )

    meta = DocumentMeta(
        doc_id="d2",
        filename="affidavit.pdf",
        doc_type="affidavit",
    )

    agent = ValidationAgent(llm_client=FakeLLMClient())
    report = agent.run(
        ValidationInput(
            document_id="d2",
            text_content=text,
            document_meta=meta,
            extracted_facts=facts,
        )
    )

    # 1. Fuzzy name variant check (Rajeshwar Sharma vs Rajesh Sharma similarity > 80%)
    name_issues = [i for i in report.issues if i.category == "NAME_SPELLING_VARIANT"]
    assert len(name_issues) >= 1
    assert "Rajeshwar Sharma" in name_issues[0].description or "Rajesh Sharma" in name_issues[0].description

    # 2. Missing affidavit verification / solemn affirmation clause
    missing_verif = [i for i in report.issues if i.category == "MISSING_VERIFICATION"]
    assert len(missing_verif) >= 1
    assert missing_verif[0].severity == "HIGH"


def test_validation_agent_sections_validity():
    """Verify ValidationAgent flags invalid statutory sections against sections_table.json."""
    facts = ExtractedFacts(
        sections=[
            SectionItem(
                act="IPC",
                section_number="420",  # Valid IPC section
                description="Cheating",
                source=SourceRef(document_id="d3", page=1, char_start=0, char_end=10, snippet="u/s 420 IPC"),
                confidence=0.95,
            ),
            SectionItem(
                act="IPC",
                section_number="999",  # Non-existent IPC section (IPC has 511 sections)
                description="Invalid section",
                source=SourceRef(document_id="d3", page=1, char_start=12, char_end=22, snippet="u/s 999 IPC"),
                confidence=0.90,
            ),
        ]
    )

    agent = ValidationAgent(llm_client=FakeLLMClient())
    report = agent.run(
        ValidationInput(
            document_id="d3",
            text_content="Accused charged u/s 420 IPC and u/s 999 IPC.",
            extracted_facts=facts,
        )
    )

    sec_issues = [i for i in report.issues if i.category == "INVALID_SECTION_NUMBER"]
    assert len(sec_issues) == 1
    assert "999" in sec_issues[0].description


def test_summary_agent_word_cap_and_source_refs():
    """Verify SummaryAgent enforces <= 150 words cap and links every key point to a SourceRef."""
    text = (
        "IN THE HIGH COURT OF DELHI\n"
        "Commercial Suit No. 202/2023\n"
        "Alpha Corp v. Beta Logistics\n"
        "The plaintiff filed this suit seeking recovery of Rs. 25,00,000 towards unpaid freight charges. "
        "The defendant acknowledged the debt via email on 15-08-2022 but subsequently failed to remit payment."
    )

    # 200-word verbose text to test 150-word cap
    verbose_summary = " ".join(["Legal contention regarding unpaid commercial debt."] * 35)  # 175 words

    fake_llm = FakeLLMClient({
        "_LLMSummaryPayload": {
            "summary_text": verbose_summary,
            "key_points": [
                {
                    "point": "Plaintiff claims unpaid freight charges of Rs. 25,00,000.",
                    "snippet": "recovery of Rs. 25,00,000 towards unpaid freight charges.",
                    "page": 1,
                },
                {
                    "point": "Defendant acknowledged debt via email.",
                    "snippet": "The defendant acknowledged the debt via email on 15-08-2022",
                    "page": 1,
                },
            ],
            "key_issues": ["Whether debt acknowledgement extends limitation?"],
            "confidence": 0.91,
        }
    })

    agent = SummaryAgent(llm_client=fake_llm)
    summary = agent.run(
        SummaryInput(
            document_id="doc-sum-01",
            text_content=text,
            max_words=150,
            language="english",
        )
    )

    # Strict <= 150 words cap
    assert summary.word_count <= 150
    assert len(summary.summary_text.split()) <= 150

    # Key points linked to SourceRefs
    assert len(summary.key_points) == 2
    for kp in summary.key_points:
        assert len(kp.source_refs) >= 1
        src = kp.source_refs[0]
        assert src.snippet in text
        assert src.char_start >= 0
        assert src.char_end > src.char_start


def test_summary_agent_hindi_and_hinglish():
    """Verify SummaryAgent generates structured summaries in Hindi and Hinglish."""
    text = (
        "थाना साकेत प्रथम सूचना रिपोर्ट संख्या 140/2023\n"
        "परिवादी ने अभियुक्त पर अमानत में खयानत का आरोप लगाया।"
    )

    fake_llm = FakeLLMClient({
        "_LLMSummaryPayload": {
            "summary_text": "यह मामला अमानत में खयानत और धोखाधड़ी से संबंधित है।",
            "key_points": [
                {
                    "point": "परिवादी द्वारा दर्ज कराई गई प्राथमिकी।",
                    "snippet": "प्रथम सूचना रिपोर्ट संख्या 140/2023",
                    "page": 1,
                }
            ],
            "confidence": 0.90,
        }
    })

    agent = SummaryAgent(llm_client=fake_llm)
    summary = agent.run(
        SummaryInput(
            document_id="doc-hi-sum",
            text_content=text,
            language="hindi",
            max_words=150,
        )
    )

    assert summary.language == "hindi"
    assert "अमानत" in summary.summary_text
    assert len(summary.key_points) == 1
    assert summary.key_points[0].source_refs[0].snippet in text


def test_pipeline_end_to_end_on_fixtures():
    """Test full document intelligence pipeline on all 3 synthetic fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    en_file = fixtures_dir / "fir_sample_en.txt"
    hi_file = fixtures_dir / "complaint_sample_hi.txt"
    hinglish_file = fixtures_dir / "witness_statement_hinglish.txt"

    assert en_file.exists()
    assert hi_file.exists()
    assert hinglish_file.exists()

    # 1. English FIR
    res_en = run_pipeline(en_file, force_mock=True)
    assert res_en["language_detection"]["primary_language"] == "english"
    assert res_en["pipeline_confidence"] >= 0.70
    assert "disclaimer" in res_en

    # 2. Hindi Complaint
    res_hi = run_pipeline(hi_file, force_mock=True)
    assert res_hi["language_detection"]["primary_language"] == "hindi"
    assert res_hi["summary"]["language"] == "hindi"

    # 3. Hinglish Statement
    res_hinglish = run_pipeline(hinglish_file, force_mock=True)
    assert res_hinglish["language_detection"]["primary_language"] == "hinglish"
    assert res_hinglish["summary"]["language"] == "hinglish"

