"""Tests for Phase 5: Orchestration, API, JWT Authentication, Tenant Isolation,
Crash Recovery, and Human-in-the-Loop Fact Review.
"""

import io
import json
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.api.main import app
from app.db.models import (
    UserModel,
    CaseModel,
    DocumentModel,
    FactModel,
    ProcessingStepModel,
    TimelineEventModel,
    Judgment,
    JudgmentChunk,
)
from app.security.jwt import create_access_token, hash_password
from app.llm.client import FakeLLMClient, FakeEmbedder
from app.orchestrator.graph import ProcessingOrchestrator

pytestmark = pytest.mark.live


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def auth_headers(db_session):
    """Create test lawyer and admin users and return authorization headers."""
    # Lawyer 1
    lawyer1 = UserModel(
        id=str(uuid.uuid4()),
        email="lawyer1@lexagent.in",
        password_hash=hash_password("Pass123!"),
        full_name="Adv. Vikram Verma",
        role="lawyer",
        is_active=True,
    )
    # Lawyer 2
    lawyer2 = UserModel(
        id=str(uuid.uuid4()),
        email="lawyer2@lexagent.in",
        password_hash=hash_password("Pass123!"),
        full_name="Adv. Meera Sen",
        role="lawyer",
        is_active=True,
    )
    # Admin
    admin = UserModel(
        id=str(uuid.uuid4()),
        email="admin@lexagent.in",
        password_hash=hash_password("AdminPass123!"),
        full_name="Super Admin",
        role="admin",
        is_active=True,
    )
    db_session.add_all([lawyer1, lawyer2, admin])
    db_session.commit()

    token1 = create_access_token(user_id=lawyer1.id, email=lawyer1.email, role="lawyer")
    token2 = create_access_token(user_id=lawyer2.id, email=lawyer2.email, role="lawyer")
    token_admin = create_access_token(user_id=admin.id, email=admin.email, role="admin")

    return {
        "lawyer1": {"Authorization": f"Bearer {token1}"},
        "lawyer1_user": lawyer1,
        "lawyer2": {"Authorization": f"Bearer {token2}"},
        "lawyer2_user": lawyer2,
        "admin": {"Authorization": f"Bearer {token_admin}"},
        "admin_user": admin,
    }


def test_phase5_jwt_auth_and_registration(client):
    """Verify user registration, login, and profile fetching with JWT."""
    # Register new lawyer
    reg_payload = {
        "email": "counsel.patil@bombaybar.in",
        "password": "Password789!",
        "full_name": "Adv. Sunita Patil",
        "role": "lawyer",
    }
    res_reg = client.post("/auth/register", json=reg_payload)
    assert res_reg.status_code == 201
    data_reg = res_reg.json()
    assert "access_token" in data_reg
    assert data_reg["role"] == "lawyer"
    token = data_reg["access_token"]

    # Verify profile
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "counsel.patil@bombaybar.in"
    assert "LEGAL DISCLAIMER" in res_me.json()["disclaimer"]

    # Login with same credentials
    login_payload = {
        "email": "counsel.patil@bombaybar.in",
        "password": "Password789!",
    }
    res_login = client.post("/auth/login", json=login_payload)
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()


def test_phase5_tenant_isolation_cross_lawyer_access(client, auth_headers):
    """Enforce tenant isolation: Lawyer B cannot access Lawyer A's cases or upload docs."""
    h_lawyer1 = auth_headers["lawyer1"]
    h_lawyer2 = auth_headers["lawyer2"]
    h_admin = auth_headers["admin"]

    # 1. Lawyer 1 creates a case
    case_payload = {
        "title": "Alpha Corp v. Beta Ltd",
        "case_number": "ARB/2023/101",
        "court": "Delhi High Court",
    }
    res_create = client.post("/cases", json=case_payload, headers=h_lawyer1)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Lawyer 1 can access their case
    res_l1_get = client.get(f"/cases/{case_id}", headers=h_lawyer1)
    assert res_l1_get.status_code == 200
    assert res_l1_get.json()["id"] == case_id

    # 2. Lawyer 2 attempts to access Lawyer 1's case -> 403 Forbidden!
    res_l2_get = client.get(f"/cases/{case_id}", headers=h_lawyer2)
    assert res_l2_get.status_code == 403
    assert "Forbidden" in res_l2_get.json()["detail"]

    # 3. Lawyer 2 attempts to upload a document to Lawyer 1's case -> 403 Forbidden!
    file_content = b"Confidential brief text."
    files = {"file": ("brief.txt", io.BytesIO(file_content), "text/plain")}
    res_l2_upload = client.post(f"/cases/{case_id}/documents", files=files, headers=h_lawyer2)
    assert res_l2_upload.status_code == 403

    # 4. Admin CAN access Lawyer 1's case
    res_admin_get = client.get(f"/cases/{case_id}", headers=h_admin)
    assert res_admin_get.status_code == 200
    assert res_admin_get.json()["id"] == case_id

    # 5. Lawyer 1 attempts to access /audit -> 403 Forbidden! (Admin only)
    res_l1_audit = client.get("/audit", headers=h_lawyer1)
    assert res_l1_audit.status_code == 403

    # 6. Admin accesses /audit -> 200 OK!
    res_admin_audit = client.get("/audit", headers=h_admin)
    assert res_admin_audit.status_code == 200
    assert res_admin_audit.json()["integrity_verified"] is True
    assert "LEGAL DISCLAIMER" in res_admin_audit.json()["disclaimer"]


def test_phase5_end_to_end_pipeline_and_views(client, auth_headers, monkeypatch):
    """End-to-end test uploading a fixture document and walking through the full pipeline."""
    h_lawyer1 = auth_headers["lawyer1"]

    # Setup Fake LLM Client
    fake_llm = FakeLLMClient(
        responses={
            "ClassificationResultSchema": {
                "doc_type": "FIR",
                "purpose": "First Information Report filed before Patiala House Court for cheating and breach of trust.",
                "filing_party": "Vikram Malhotra",
                "court_named": "Patiala House Courts, New Delhi",
                "relief_sought": "Registration of criminal case and investigation",
            },
            "_RawExtractedFactsPayload": {
                "parties": [
                    {
                        "name": "Vikramaditya Verma",
                        "role": "complainant",
                        "snippet": "Name: Vikramaditya Verma, S/o Late Shri R. K. Verma",
                        "page": 1,
                        "confidence": 0.95,
                    },
                    {
                        "name": "Rajeshwar Sharma",
                        "role": "accused",
                        "snippet": "Name: Rajeshwar Sharma, R/o Sector 21, Noida, Uttar Pradesh",
                        "page": 1,
                        "confidence": 0.95,
                    },
                ],
                "dates": [
                    {
                        "date_str": "10-03-2023",
                        "description": "Date of transaction and fraud",
                        "snippet": "Date: 10-03-2023, Time: 14:30 hrs",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
                "sections": [
                    {
                        "act": "IPC",
                        "section_number": "420",
                        "snippet": "Section 420, Section 406 of the Indian Penal Code (IPC)",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
                "amounts": [
                    {
                        "value": 1500000.0,
                        "currency": "INR",
                        "context": "Misappropriated investment amount",
                        "snippet": "Rs. 15,00,000 (Rupees Fifteen Lakhs)",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
                "statements": [
                    {
                        "statement_type": "complaint",
                        "speaker": "Vikramaditya Verma",
                        "role": "complainant",
                        "recorded_on": "15-03-2023",
                        "recorded_by": "Sub-Inspector Rakesh Nehra",
                        "content": "Accused fraudulently induced complainant to invest Rs 15 Lakhs on forged title deeds.",
                        "snippet": "The complainant Vikramaditya Verma states that on 10-03-2023, the accused Rajeshwar Sharma fraudulently induced the complainant to invest an amount of Rs. 15,00,000",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
            },
            "_LLMValidationReview": {
                "logical_issues": [],
                "confidence": 0.92,
            },
            "_LLMSummaryPayload": {
                "summary_text": "FIR lodged by Vikramaditya Verma against Rajeshwar Sharma for cheating under Section 420 IPC involving misappropriation of Rs. 15,00,000.",
                "key_points": [
                    {
                        "point": "Complainant transferred Rs. 15 Lakhs for property in Saket.",
                        "snippet": "Rs. 15,00,000 (Rupees Fifteen Lakhs)",
                        "page": 1,
                    }
                ],
                "key_issues": ["Cheating under Section 420 IPC", "Recovery of Rs. 15,00,000"],
                "relief_sought": "Investigation and recovery",
                "confidence": 0.92,
            },
        }
    )

    # Monkeypatch LLM in orchestrator and llm client factory
    monkeypatch.setattr("app.llm.client.get_llm_client", lambda: fake_llm)
    monkeypatch.setattr("app.orchestrator.graph.get_llm_client", lambda: fake_llm)

    # 1. Create Case
    res_case = client.post(
        "/cases",
        json={"title": "Vikram Malhotra v. Devendra Patil", "court": "Patiala House Courts"},
        headers=h_lawyer1,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 2. Upload Document
    fir_file_path = FIXTURES_DIR / "fir_sample_en.txt"
    with open(fir_file_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("fir_sample_en.txt", io.BytesIO(file_bytes), "text/plain")}
    res_upload = client.post(f"/cases/{case_id}/documents", files=files, headers=h_lawyer1)
    assert res_upload.status_code == 202
    doc_id = res_upload.json()["document_id"]
    assert "LEGAL DISCLAIMER" in res_upload.json()["disclaimer"]

    # 3. Check Document Status
    res_status = client.get(f"/documents/{doc_id}/status", headers=h_lawyer1)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["document_id"] == doc_id
    assert status_data["status"] in ["done", "needs_review", "pending"]
    step_names = [s["step_name"] for s in status_data["steps"]]
    assert "ocr" in step_names
    assert "fact_extraction" in step_names

    # 4. Check Document Summary
    res_summ = client.get(f"/documents/{doc_id}/summary", headers=h_lawyer1)
    assert res_summ.status_code == 200
    assert "FIR lodged by Vikramaditya Verma" in (res_summ.json()["summary"] or "")
    assert "LEGAL DISCLAIMER" in res_summ.json()["disclaimer"]

    # 5. Check Document Facts (with SourceRef provenance)
    res_facts = client.get(f"/documents/{doc_id}/facts", headers=h_lawyer1)
    assert res_facts.status_code == 200
    facts_data = res_facts.json()
    assert facts_data["total_facts"] >= 1
    sample_fact = facts_data["facts"][0]
    assert "source_ref" in sample_fact
    assert "snippet" in sample_fact["source_ref"]
    assert "LEGAL DISCLAIMER" in facts_data["disclaimer"]

    # 6. Check Document Validation
    res_val = client.get(f"/documents/{doc_id}/validation", headers=h_lawyer1)
    assert res_val.status_code == 200
    assert "total_issues" in res_val.json()

    # 7. Check Case Dashboard
    res_dash = client.get(f"/cases/{case_id}/dashboard", headers=h_lawyer1)
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    assert dash_data["total_documents"] == 1
    assert dash_data["total_facts"] >= 1
    assert "LEGAL DISCLAIMER" in dash_data["disclaimer"]


def test_phase5_fact_review_workflow(client, auth_headers, db_session):
    """Test lawyer reviewing/correcting an extracted fact."""
    h_lawyer1 = auth_headers["lawyer1"]
    lawyer1_user = auth_headers["lawyer1_user"]

    # Setup case, doc, and fact
    case = CaseModel(user_id=lawyer1_user.id, title="Review Test Matter")
    db_session.add(case)
    db_session.commit()

    doc = DocumentModel(case_id=case.id, filename="doc.pdf", sha256_hash="abc", status="done")
    db_session.add(doc)
    db_session.commit()

    fact = FactModel(
        document_id=doc.id,
        case_id=case.id,
        category="amount",
        item_data=json.dumps({"value": 1000000.0, "currency": "INR"}),
        source_ref=json.dumps({"document_id": doc.id, "page": 1, "snippet": "Rs. 10 Lakhs"}),
        confidence=0.65,  # Low confidence, flagged for human review
        is_reviewed=False,
    )
    db_session.add(fact)
    db_session.commit()

    # Lawyer reviews and corrects the fact
    correction_payload = {
        "action": "corrected",
        "correction_data": {
            "value": 1250000.0,
            "currency": "INR",
            "notes": "Amended after verifying bank deposit slip dated 12-04-2023",
        },
    }
    res_review = client.post(f"/facts/{fact.id}/review", json=correction_payload, headers=h_lawyer1)
    assert res_review.status_code == 200
    rev_data = res_review.json()
    assert rev_data["fact_id"] == fact.id
    assert rev_data["is_reviewed"] is True
    assert rev_data["review_action"] == "corrected"
    assert rev_data["correction_data"]["value"] == 1250000.0
    assert "LEGAL DISCLAIMER" in rev_data["disclaimer"]

    # Check that GET /documents/{id}/facts shows the reviewed status
    res_facts = client.get(f"/documents/{doc.id}/facts", headers=h_lawyer1)
    assert res_facts.status_code == 200
    updated_fact = [f for f in res_facts.json()["facts"] if f["fact_id"] == fact.id][0]
    assert updated_fact["is_reviewed"] is True
    assert updated_fact["review_action"] == "corrected"
    assert updated_fact["correction_data"]["value"] == 1250000.0


def test_phase5_crash_and_resume(db_session):
    """Verify that ProcessingOrchestrator resumes from DB state after simulated crash."""
    doc_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())

    doc = DocumentModel(
        id=doc_id,
        case_id=case_id,
        filename="test_crash.txt",
        sha256_hash="hash123",
        status="running",
    )
    db_session.add(doc)
    db_session.commit()

    # Simulate step 1 ('ocr') and step 2 ('language_detection') having completed before crash
    cached_ocr_payload = {
        "document_id": doc_id,
        "pages": [{"page_number": 1, "text": "FIR No. 101/2023 PS Connaught Place under Section 420 IPC.", "confidence": 0.98}],
        "overall_confidence": 0.98,
    }
    cached_lang_payload = {
        "document_id": doc_id,
        "primary_language": "english",
        "pages": [{"page_number": 1, "language": "english", "script": "Latin"}],
    }

    step_ocr = ProcessingStepModel(
        document_id=doc_id,
        case_id=case_id,
        step_name="ocr",
        status="done",
        attempt=1,
        state_payload=json.dumps(cached_ocr_payload),
    )
    step_lang = ProcessingStepModel(
        document_id=doc_id,
        case_id=case_id,
        step_name="language_detection",
        status="done",
        attempt=1,
        state_payload=json.dumps(cached_lang_payload),
    )
    # Simulate step 3 crashing
    step_class = ProcessingStepModel(
        document_id=doc_id,
        case_id=case_id,
        step_name="classifier",
        status="failed",
        attempt=1,
        error_message="Simulated process killed / SIGKILL",
    )
    db_session.add_all([step_ocr, step_lang, step_class])
    db_session.commit()

    # Initialize orchestrator with Fake LLM Client
    fake_llm = FakeLLMClient(
        responses={
            "ClassificationResultSchema": {
                "doc_type": "FIR",
                "purpose": "First Information Report regarding cheating.",
                "filing_party": "State",
                "court_named": "Magistrate Court",
                "relief_sought": "Prosecution",
            },
            "_RawExtractedFactsPayload": {
                "parties": [
                    {
                        "name": "State",
                        "role": "complainant",
                        "snippet": "PS Connaught Place under Section 420 IPC",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
                "sections": [
                    {
                        "act": "IPC",
                        "section_number": "420",
                        "snippet": "Section 420 IPC",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ],
            },
            "_LLMValidationReview": {
                "logical_issues": [],
                "confidence": 0.90,
            },
            "_LLMSummaryPayload": {
                "summary_text": "Cheating case registered at PS Connaught Place.",
                "key_points": [
                    {
                        "point": "Registered under Section 420 IPC",
                        "snippet": "Section 420 IPC",
                        "page": 1,
                    }
                ],
                "confidence": 0.90,
            },
        }
    )

    orchestrator = ProcessingOrchestrator(db_session=db_session, llm_client=fake_llm)

    # Resume document processing
    res_state = orchestrator.resume_document_processing(doc_id)

    # Verify that cached OCR and Language results were reused without repeating OCR
    assert res_state["ocr_result"]["document_id"] == doc_id
    assert res_state["language_result"]["primary_language"] == "english"

    # Verify that classifier was retried and succeeded
    assert res_state["classifier_result"]["document_meta"]["doc_type"] == "FIR"

    # Verify document completed successfully
    assert res_state["status"] in ["done", "needs_review"]
    refreshed_doc = db_session.get(DocumentModel, doc_id)
    assert refreshed_doc.status in ["done", "needs_review"]


def test_phase5_legal_research_endpoint(client, auth_headers, db_session):
    """Test POST /research endpoint with grounded answer and citations."""
    h_lawyer = auth_headers["lawyer1"]

    # Seed a precedent judgment in DB
    j = Judgment(
        title="Sanjay Chandra v. CBI",
        court="Supreme Court of India",
        date="2012-01-23",
        citation="(2012) 1 SCC 40",
        summary="Bail jurisprudence in economic offences under Section 420 IPC.",
        outcome="Bail Granted",
        full_text="Bail is the rule and jail is the exception. Pre-trial detention cannot be punitive.",
    )
    db_session.add(j)
    db_session.commit()

    chunk = JudgmentChunk(
        judgment_id=j.id,
        chunk_index=0,
        text="Bail is the rule and jail is the exception. Even in economic offences, pre-trial detention should not be punitive.",
    )
    db_session.add(chunk)
    db_session.commit()

    research_payload = {
        "query": "regular bail considerations in Section 420 IPC",
        "top_k": 3,
    }
    res = client.post("/research", json=research_payload, headers=h_lawyer)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "citations" in data
    assert "LEGAL DISCLAIMER" in data["disclaimer"]
