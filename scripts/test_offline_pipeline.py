"""Live pipeline execution test with Ollama offline.

Demonstrates:
1. No silent fallbacks: every agent reports its truthful engine ('rules', 'pymupdf')
2. Step statuses: 'fallback' / 'needs_review' / 'rule_based'
3. Needs human review flagged: needs_human_review=True
4. Audit log rows written with HMAC cryptographic integrity
5. Processing step rows in DB recording engine, status, and fallback_taken
"""

import json
import os
import sys
from pathlib import Path

LEXAGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LEXAGENT_DIR))

db_path = (LEXAGENT_DIR / "lexagent.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
os.environ["DB_URL"] = f"sqlite:///{db_path.as_posix()}"
os.environ["ENVIRONMENT"] = "production"

from app.db.session import init_db, get_session_factory
from app.db.models import ProcessingStepModel, AuditLogModel, DocumentModel, CaseModel
from app.orchestrator.graph import ProcessingOrchestrator
from app.security.audit import AuditLogger

TEST_LEGAL_DOC = """
IN THE COURT OF THE CHIEF METROPOLITAN MAGISTRATE, SAKET COURTS, NEW DELHI
Criminal Complaint Case No. 892/2024

IN THE MATTER OF:
Rameshwar Prasad Sharma, S/o Late Shri B.L. Sharma
R/o H.No. 44, Greater Kailash-I, New Delhi ... Complainant

VERSUS

Kuldeep Singh, S/o Gurmeet Singh
R/o Flat No. 204, Saket Residency, New Delhi ... Accused

COMPLAINT UNDER SECTION 420 AND 406 OF THE INDIAN PENAL CODE, 1860

MOST RESPECTFULLY SHOWETH:
1. That the complainant entered into a formal business procurement contract with the accused on 15/01/2023.
2. That pursuant to the agreed covenants, complainant disbursed an advance payment of Rs. 15,00,000 via RTGS on 22/02/2023.
3. That on 18/03/2023, witness Ramesh Verma stated in his statement under Section 161 CrPC:
   "The accused Kuldeep Singh was present at the Saket warehouse at 9 PM on 10th March."
4. That contrary to representations, accused did not deliver the goods and misappropriated the funds.
5. That statutory demand notice was issued on 12/04/2023, yet no payment was returned.
6. Hence, this complaint is filed praying for summoning and trial of the accused under Sections 420 and 406 IPC.
"""

def run_offline_test():
    init_db()
    factory = get_session_factory()
    session = factory()

    orchestrator = ProcessingOrchestrator(db_session=session)

    doc_id = "doc-offline-test-001"
    case_id = "case-test-live-fail"

    print("=" * 70)
    print("  RUNNING PIPELINE WITH OLLAMA OFFLINE")
    print(f"  Target Document ID: {doc_id}")
    print("=" * 70)

    # Ensure Case and Document exist
    c = session.get(CaseModel, case_id)
    if not c:
        c = CaseModel(id=case_id, title="Test Criminal Case", case_number="CC 892/2024")
        session.add(c)
        session.commit()

    d = session.get(DocumentModel, doc_id)
    if not d:
        d = DocumentModel(id=doc_id, case_id=case_id, filename="saket_complaint_420.txt", sha256_hash="testhash123")
        session.add(d)
        session.commit()

    result = orchestrator.process_document(
        document_id=doc_id,
        case_id=case_id,
        filename="saket_complaint_420.txt",
        raw_text=TEST_LEGAL_DOC,
    )

    print("\n[+] Pipeline Result:")
    print(f"    Status: {result.get('status')}")
    print(f"    Needs Human Review: {result.get('needs_human_review')}")
    print(f"    Confidence: {result.get('confidence')}")

    # Inspect processing_steps in DB
    steps = session.query(ProcessingStepModel).filter(ProcessingStepModel.document_id == doc_id).all()
    print(f"\n[+] Processing Steps Recorded in DB ({len(steps)} steps):")
    for s in steps:
        print(f"    Step: {s.step_name:<20} | Status: {s.status:<10} | Engine: {s.engine:<10} | Fallback: {s.fallback_taken}")

    # Inspect audit_logs in memory/DB
    audit_records = AuditLogger.get_records()
    print(f"\n[+] Audit Log Records ({len(audit_records)} total events):")
    for a in audit_records[-6:]:
        print(f"    Event: {a.event_type:<25} | Actor: {a.actor:<30} | Status: {a.status}")

    # Print Summary & Extraction outputs showing explicit offline fallback
    if "summary_result" in result and result["summary_result"]:
        sm = result["summary_result"]
        print(f"\n[+] Summary Agent Output (Truthful Fallback):")
        print(f"    Engine: {sm.get('engine')} | Fallback Taken: {sm.get('fallback_taken')} | Status: {sm.get('status')}")
        print(f"    Error Message: {sm.get('error_message')}")
        print(f"    Summary: {sm.get('summary_text')}")

    if "facts_result" in result and result["facts_result"]:
        fm = result["facts_result"]
        print(f"\n[+] Fact Extraction Agent Output (Deterministic Engine):")
        print(f"    Engine: {fm.get('engine')} | Fallback Taken: {fm.get('fallback_taken')} | Status: {fm.get('status')}")
        print(f"    Error Message: {fm.get('error_message')}")
        facts = fm.get("extracted_facts", {})
        print(f"    Parties Extracted: {len(facts.get('parties', []))}")
        print(f"    Sections Extracted: {len(facts.get('sections', []))}")
        print(f"    Amounts Extracted: {len(facts.get('amounts', []))}")
        print(f"    Dates Extracted: {len(facts.get('dates', []))}")

    print("\n" + "=" * 70)
    print("  TESTING CASE-LEVEL AGENTS (TIMELINE, CONTRADICTION, SIMILAR CASES)")
    print("=" * 70)
    case_res = orchestrator.process_case(case_id)
    print(f"[+] Case Processing Result:")
    print(f"    Timeline Events: {case_res.get('timeline_events_count')}")
    print(f"    Contradictions: {case_res.get('contradictions_count')}")
    print(f"    Similar Cases: {case_res.get('similar_cases_count')}")

    session.close()

if __name__ == "__main__":
    run_offline_test()
