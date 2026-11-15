"""Unit and integration tests for LexAgent Phase B: Multilingual Translation Subsystem.

Verifies:
1. Seed legal glossary completeness (40+ terms, EN/HI/MR).
2. Protected tokens masking and verbatim restoration across translations.
3. Sentence-level alignment with exact SourceRef character offset integrity.
4. Glossary enforcement during translation.
5. Back-translation divergence detection and human review escalation.
6. Content-hash translation caching.
7. Document and summary translation API endpoints with tenant isolation.
"""

import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.agents.translation import TranslationAgent
from app.db.models import (
    CaseModel,
    DocumentModel,
    DocumentPage as DocumentPageModel,
    SummaryModel,
    UserModel,
)
from app.llm.translator import FakeTranslator, LocalLLMTranslator
from app.schemas.translation import TranslationInput
from app.security.jwt import create_access_token, hash_password


# =============================================================================
# Test 1: Seed Legal Glossary Completeness
# =============================================================================
def test_legal_glossary_structure_and_coverage():
    glossary_path = Path(__file__).resolve().parent.parent / "data" / "glossary" / "legal_terms.json"
    if not glossary_path.exists():
        glossary_path = Path("data") / "glossary" / "legal_terms.json"
    assert os.path.exists(glossary_path), f"Glossary file missing at {glossary_path}"

    with open(glossary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    terms = data.get("terms", [])
    assert len(terms) >= 40, f"Expected at least 40 terms, found {len(terms)}"

    for term in terms:
        assert "english" in term and term["english"].strip()
        assert "hindi" in term and term["hindi"].strip()
        assert "marathi" in term and term["marathi"].strip()

    # Verify key Indian legal terms exist
    english_terms = {t["english"].lower() for t in terms}
    required_keywords = [
        "first information report",
        "chargesheet",
        "bail",
        "anticipatory bail",
        "affidavit",
        "summons",
        "warrant",
        "cognizable offence",
        "cross-examination",
        "deposition",
        "panchnama",
    ]
    for kw in required_keywords:
        assert kw in english_terms, f"Mandatory legal keyword '{kw}' missing from glossary."


# =============================================================================
# Test 2: Protected Tokens Masking & Restoration
# =============================================================================
def test_protected_tokens_masking_and_restoration():
    agent = TranslationAgent(translator=FakeTranslator())

    text = (
        "The accused filed an application under Section 420 IPC and Section 302 of Indian Penal Code "
        "on 15/03/2023 for FIR No. 45/2022 involving an amount of Rs. 15,00,000."
    )

    masked_text, protected_map = agent.mask_protected_tokens(text)

    # Check that placeholders are inserted
    assert "[[PROT_0]]" in masked_text
    assert "Section 420 IPC" not in masked_text
    assert "15/03/2023" not in masked_text
    assert "Rs. 15,00,000" not in masked_text
    assert "FIR No. 45/2022" not in masked_text

    # Verify protected map captures all original tokens
    values = list(protected_map.values())
    assert any("Section 420 IPC" in v for v in values)
    assert any("Section 302 of Indian Penal Code" in v for v in values)
    assert any("15/03/2023" in v for v in values)
    assert any("Rs. 15,00,000" in v for v in values)
    assert any("FIR No. 45/2022" in v for v in values)

    # Check restoration
    restored, missing = agent.restore_protected_tokens(masked_text, protected_map)
    assert not missing
    assert restored == text


# =============================================================================
# Test 3: Sentence-Level SourceRef Alignment Integrity
# =============================================================================
def test_sentence_level_sourceref_alignment():
    agent = TranslationAgent(translator=FakeTranslator())

    page_text = (
        "The complainant lodged an FIR against the accused. "
        "The police submitted a chargesheet under Section 420 IPC on 12/05/2022. "
        "The learned Magistrate granted regular bail."
    )

    inp = TranslationInput(
        document_id="doc-test-101",
        content=page_text,
        source_language="en",
        target_language="hi",
    )
    result = agent.run(inp)

    assert result.document_id == "doc-test-101"
    assert len(result.pages) == 1
    page = result.pages[0]

    # Must have 3 aligned sentences
    assert len(page.alignments) == 3

    for al in page.alignments:
        ref = al.source_ref
        assert ref.document_id == "doc-test-101"
        assert ref.page == 1
        # Character offsets must match page text exactly
        extracted = page_text[ref.char_start : ref.char_end]
        assert extracted == ref.snippet
        assert ref.snippet == al.source_sentence
        # Target sentence must contain translated text
        assert al.target_sentence


# =============================================================================
# Test 4: Glossary Enforcement in Translation
# =============================================================================
def test_glossary_enforcement_in_translation():
    agent = TranslationAgent(translator=FakeTranslator())

    text = "The applicant filed an affidavit seeking anticipatory bail before the chargesheet was filed."
    inp = TranslationInput(
        document_id="doc-glossary-test",
        content=text,
        source_language="en",
        target_language="hi",
        preserve_glossary=True,
    )
    result = agent.run(inp)

    full_trans = result.full_translated_text
    # Check that glossary translations are present in translated text
    assert "शपथ पत्र" in full_trans  # affidavit
    assert "अग्रिम जमानत" in full_trans  # anticipatory bail
    assert "आरोप पत्र" in full_trans  # chargesheet


# =============================================================================
# Test 5: Back-Translation Divergence Detection
# =============================================================================
def test_back_translation_divergence_detection():
    # Use FakeTranslator with simulate_divergence=True to simulate corrupted or hallucinated translation
    divergent_translator = FakeTranslator(simulate_divergence=True)
    agent = TranslationAgent(translator=divergent_translator)

    text = "The witness appeared before the court and recorded a deposition under Section 164 CrPC."
    inp = TranslationInput(
        document_id="doc-divergent-test",
        content=text,
        source_language="en",
        target_language="hi",
        verify_backtranslation=True,
    )
    result = agent.run(inp)

    # Should flag back_translation_divergence
    assert result.needs_human_review is True
    assert result.confidence < 0.75
    divergence_issues = [i for i in result.issues if i.category == "back_translation_divergence"]
    assert len(divergence_issues) > 0
    assert divergence_issues[0].severity == "HIGH"


# =============================================================================
# Test 6: Content-Hash Translation Caching
# =============================================================================
def test_translation_caching():
    agent = TranslationAgent(translator=FakeTranslator())

    text = "The petitioner filed a revision petition against the interim order."
    inp = TranslationInput(
        document_id="doc-cache-test",
        content=text,
        source_language="en",
        target_language="hi",
    )

    result1 = agent.run(inp)
    assert result1.content_hash is not None

    # Second call with identical input should return cached object
    result2 = agent.run(inp)
    assert result1.content_hash == result2.content_hash
    assert result1.full_translated_text == result2.full_translated_text


# =============================================================================
# Test 7: API Endpoints (POST /documents/{id}/translate & GET /documents/{id}/translations/{lang})
# =============================================================================
def test_document_translation_api_endpoints(client: TestClient, db_session):
    # Setup test lawyer and case
    lawyer = UserModel(
        email="trans_lawyer@example.com",
        full_name="Advocate Test",
        password_hash=hash_password("testpass123"),
        role="lawyer",
    )
    db_session.add(lawyer)
    db_session.commit()

    case = CaseModel(
        title="State v. Ramesh",
        case_number="CC 101/2023",
        court="Metropolitan Magistrate Court",
        user_id=lawyer.id,
    )
    db_session.add(case)
    db_session.commit()

    doc = DocumentModel(
        case_id=case.id,
        filename="chargesheet.pdf",
        sha256_hash="dummy_chargesheet_hash_12345",
        doc_type="chargesheet",
        status="done",
        page_count=1,
    )
    db_session.add(doc)
    db_session.commit()

    page = DocumentPageModel(
        document_id=doc.id,
        page_number=1,
        text="The police filed chargesheet under Section 420 IPC on 10/10/2023. Regular bail was denied.",
        confidence=0.95,
        language="en",
    )
    db_session.add(page)
    db_session.commit()

    token = create_access_token(user_id=lawyer.id, email=lawyer.email, role="lawyer")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Translate document
    resp = client.post(
        f"/documents/{doc.id}/translate",
        json={"target_language": "hi", "source_language": "en"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["document_id"] == doc.id
    assert data["target_language"] == "hi"
    assert "Section 420 IPC" in data["full_translated_text"]
    assert "10/10/2023" in data["full_translated_text"]
    assert len(data["pages"]) == 1
    assert "disclaimer" in data

    # 2. Retrieve cached translation
    get_resp = client.get(
        f"/documents/{doc.id}/translations/hi",
        headers=headers,
    )
    assert get_resp.status_code == 200, get_resp.text
    cached_data = get_resp.json()
    assert cached_data["full_translated_text"] == data["full_translated_text"]
    assert cached_data["document_id"] == doc.id


# =============================================================================
# Test 8: Case Summary Translation API Endpoint
# =============================================================================
def test_case_summary_translation_api_endpoint(client: TestClient, db_session):
    lawyer = UserModel(
        email="summary_lawyer@example.com",
        full_name="Advocate Summary",
        password_hash=hash_password("testpass123"),
        role="lawyer",
    )
    db_session.add(lawyer)
    db_session.commit()

    case = CaseModel(
        title="Patil v. State",
        case_number="BA 404/2023",
        court="High Court of Bombay",
        user_id=lawyer.id,
    )
    db_session.add(case)
    db_session.commit()

    summary = SummaryModel(
        case_id=case.id,
        summary_text="Applicant seeks anticipatory bail in connection with FIR No. 88/2023 under Section 420 IPC.",
        disclaimer="Standard disclaimer",
    )
    db_session.add(summary)
    db_session.commit()

    token = create_access_token(user_id=lawyer.id, email=lawyer.email, role="lawyer")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        f"/cases/{case.id}/summary/translate",
        json={"target_language": "mr", "source_language": "en"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["case_id"] == case.id
    assert data["target_language"] == "mr"
    assert "FIR No. 88/2023" in data["translated_summary"]
    assert "Section 420 IPC" in data["translated_summary"]
    assert "disclaimer" in data


# =============================================================================
# Test 9: Tenant Isolation on Translation
# =============================================================================
def test_translation_tenant_isolation(client: TestClient, db_session):
    lawyer1 = UserModel(
        email="lawyer1@example.com",
        full_name="Lawyer One",
        password_hash=hash_password("pass1"),
        role="lawyer",
    )
    lawyer2 = UserModel(
        email="lawyer2@example.com",
        full_name="Lawyer Two",
        password_hash=hash_password("pass2"),
        role="lawyer",
    )
    db_session.add_all([lawyer1, lawyer2])
    db_session.commit()

    case1 = CaseModel(title="Case 1", user_id=lawyer1.id)
    db_session.add(case1)
    db_session.commit()

    doc1 = DocumentModel(
        case_id=case1.id,
        filename="doc1.pdf",
        sha256_hash="dummy_hash_doc1",
        status="done",
    )
    db_session.add(doc1)
    db_session.commit()

    # Lawyer 2 token
    token2 = create_access_token(user_id=lawyer2.id, email=lawyer2.email, role="lawyer")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Lawyer 2 attempts to translate Lawyer 1's document -> 403 Forbidden
    resp = client.post(
        f"/documents/{doc1.id}/translate",
        json={"target_language": "hi"},
        headers=headers2,
    )
    assert resp.status_code == 403

    # Lawyer 2 attempts to fetch Lawyer 1's document translations -> 403 Forbidden
    resp_get = client.get(
        f"/documents/{doc1.id}/translations/hi",
        headers=headers2,
    )
    assert resp_get.status_code == 403

    # Lawyer 2 attempts to translate Lawyer 1's case summary -> 403 Forbidden
    resp_summary = client.post(
        f"/cases/{case1.id}/summary/translate",
        json={"target_language": "hi"},
        headers=headers2,
    )
    assert resp_summary.status_code == 403
