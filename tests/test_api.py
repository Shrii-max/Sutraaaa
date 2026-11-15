"""Tests for FastAPI endpoints, middleware, disclaimer injection, and audit trail."""

import io
import pytest
from app.db.models import PrecedentCaseModel

pytestmark = pytest.mark.live


def test_api_health_endpoint(client):
    """Verify health endpoint returns local-only privacy indicators."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["local_only_mode"] is True
    assert data["telemetry_enabled"] is False
    assert "LEGAL DISCLAIMER" in data["disclaimer"]
    # Check middleware header
    assert "X-Legal-Disclaimer" in res.headers


def test_api_precedent_seeding_and_retrieval(client):
    """Verify seeding and listing of verified precedents."""
    cases_payload = [
        {
            "case_title": "Salem Advocate Bar Association v. Union of India",
            "citation": "(2005) 6 SCC 344",
            "court": "Supreme Court of India",
            "judgment_date": "2005-08-02",
            "summary": "Civil procedure code amendments regarding written statement filing deadlines.",
            "ratio_decidendi": "Order VIII Rule 1 CPC 90-day time limit is directory and not mandatory.",
        }
    ]
    res_seed = client.post("/api/v1/cases/seed", json=cases_payload)
    assert res_seed.status_code == 200
    assert res_seed.json()["seeded_count"] == 1

    res_list = client.get("/api/v1/precedents")
    assert res_list.status_code == 200
    assert res_list.json()["count"] >= 1


def test_api_document_upload(client):
    """Verify document upload, AES-GCM encryption, chunking, and metadata response."""
    file_content = b"Legal Notice under Section 80 CPC issued to Government of India on 01-04-2023."
    files = {"file": ("notice.txt", io.BytesIO(file_content), "text/plain")}

    res = client.post("/api/v1/documents/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "document_id" in data
    assert data["status"] == "encrypted_and_stored"
    assert data["page_count"] == 1
    assert data["chunks_count"] >= 1


@pytest.mark.live
def test_api_analyze_direct_text(client):
    """Verify direct text legal analysis through API (requires live LLM)."""
    payload = {
        "raw_text": (
            "Arbitration dispute between TechSolutions Ltd and State Power Corp. "
            "Arbitration notice issued on 12-05-2023 under Section 21 of ACA 1996."
        ),
        "filename": "arbitration_notice.txt",
    }
    res = client.post("/api/v1/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "case_summary" in data
    assert "document_extraction" in data
    assert "timeline_analysis" in data
    assert "precedents" in data
    assert "risk_assessment" in data
    assert "LEGAL DISCLAIMER" in data["disclaimer"]
    assert 0.0 <= data["confidence"] <= 1.0


def test_api_audit_trail_and_verification(client):
    """Verify append-only audit trail retrieval and cryptographic HMAC integrity verification."""
    # Retrieve audit trail
    res_logs = client.get("/api/v1/audit/logs")
    assert res_logs.status_code == 200
    assert res_logs.json()["total_records"] >= 1

    # Verify HMAC hash chain integrity
    res_verify = client.get("/api/v1/audit/verify")
    assert res_verify.status_code == 200
    assert res_verify.json()["integrity_verified"] is True
    assert res_verify.json()["hash_chain_status"] == "INTACT"

