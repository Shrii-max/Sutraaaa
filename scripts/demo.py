"""End-to-End Demonstration Script for LexAgent.

Loads sample documents (English FIR, Hindi Complaint, Hinglish Witness Statement),
ingests sample precedent judgments and statutory provisions, runs the full LangGraph
multi-agent pipeline, and pretty-prints the synthesized legal intelligence.

Run:
    python -m scripts.demo
"""

import sys
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.security.crypto import encrypt_file
from app.db.models import Base, CaseModel, DocumentModel
from app.ingestion.judgments import load_judgments_from_jsonl, ingest_judgment_items
from app.ingestion.statutes import load_statutes_from_jsonl, ingest_statute_items
from app.orchestrator.graph import ProcessingOrchestrator
from app.services.case_manager import CaseManager
from app.llm.client import FakeLLMClient, FakeEmbedder, get_llm_client
from app.config import get_settings

ROOT_DIR = Path(__file__).parent.parent
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"


def is_llm_reachable(base_url: str) -> bool:
    """Quick probe to check if local Ollama/vLLM server is active."""
    import httpx
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/models", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def run_demo():
    print("=" * 80)
    print("LEXAGENT: LOCAL MULTI-AGENT LEGAL DOCUMENT INTELLIGENCE SYSTEM")
    print("=" * 80)

    settings = get_settings()
    llm_online = is_llm_reachable(settings.LLM_BASE_URL)
    if llm_online:
        print(f"Connected to local LLM server at: {settings.LLM_BASE_URL} (Model: {settings.LLM_MODEL})")
        demo_llm = None
        demo_embedder = None
    else:
        print(f"Local LLM runtime not detected at {settings.LLM_BASE_URL}.")
        print("Using high-fidelity deterministic offline LLM and BGE-M3 Embedder for demonstration.")
        demo_llm = FakeLLMClient(
            responses={
                "ClassificationResultSchema": {
                    "doc_type": "FIR",
                    "purpose": "First Information Report lodged before Saket Court regarding criminal cheating and forgery.",
                    "filing_party": "Vikramaditya Verma",
                    "court_named": "Saket District Court, New Delhi",
                    "relief_sought": "Registration of FIR and criminal proceedings",
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
                            "date_str": "15-03-2023",
                            "description": "FIR registration date",
                            "snippet": "Date & Time: 15-03-2023 at 11:30 hrs",
                            "page": 1,
                            "confidence": 0.95,
                        },
                        {
                            "date_str": "10-03-2023",
                            "description": "Occurrence of offence",
                            "snippet": "Date: 10-03-2023, Time: 14:30 hrs",
                            "page": 1,
                            "confidence": 0.95,
                        },
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
                            "context": "Misappropriated sum",
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
                            "content": "Accused induced complainant to invest Rs 15 Lakhs on forged title deeds.",
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
                    "summary_text": "FIR lodged by Vikramaditya Verma against Rajeshwar Sharma for cheating under Section 420/406 IPC involving misappropriation of Rs. 15,00,000 towards commercial property in Saket.",
                    "key_points": [
                        {
                            "point": "Complainant transferred Rs. 15 Lakhs via RTGS for Saket property.",
                            "snippet": "Rs. 15,00,000 (Rupees Fifteen Lakhs)",
                            "page": 1,
                        }
                    ],
                    "key_issues": ["Cheating under Section 420 IPC", "Criminal Breach of Trust under Section 406 IPC"],
                    "relief_sought": "Investigation and recovery",
                    "confidence": 0.92,
                },
            }
        )
        demo_embedder = FakeEmbedder(1024)

    print("Initializing isolated local demonstration database...\n")
    engine = create_engine("sqlite:///demo_lexagent.db", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Ingest Sample Precedents and Bare Acts
    print("[1/4] Ingesting verified Indian precedent judgments and statutory provisions...")
    judgments_file = FIXTURES_DIR / "sample_judgments.jsonl"
    statutes_file = FIXTURES_DIR / "sample_statutes.jsonl"

    j_items = load_judgments_from_jsonl(judgments_file)
    j_count, c_count = ingest_judgment_items(j_items, session=session, embedder=demo_embedder)
    print(f"  -> Ingested {j_count} judicial judgments ({c_count} paragraph chunks).")

    s_items = load_statutes_from_jsonl(statutes_file)
    s_count = ingest_statute_items(s_items, session=session, embedder=demo_embedder)
    print(f"  -> Ingested {s_count} bare-act statutory sections.\n")

    # 2. Create Case File
    print("[2/4] Initializing Case File: 'Vikramaditya Verma v. Rajeshwar Sharma'...")
    case = CaseModel(
        title="Vikramaditya Verma v. Rajeshwar Sharma & Ors.",
        case_number="FIR No. 0142/2023 PS Saket",
        court="Sessions Court, Saket District Centre, New Delhi",
        status="open",
    )
    session.add(case)
    session.commit()
    print(f"  -> Case created (ID: {case.id})\n")

    # 3. Load and Ingest Sample Documents
    print("[3/4] Ingesting documents into case file:")
    doc_files = [
        ("fir_sample_en.txt", "FIR under Section 420/406 IPC (English)"),
        ("complaint_sample_hi.txt", "Private Complaint u/s 156(3) CrPC (Hindi)"),
        ("witness_statement_hinglish.txt", "Witness Statement u/s 161 CrPC (Hinglish)"),
    ]

    for fname, desc in doc_files:
        fpath = FIXTURES_DIR / fname
        raw_bytes = fpath.read_bytes()
        encrypted = encrypt_file(raw_bytes)
        doc = DocumentModel(
            case_id=case.id,
            filename=fname,
            encrypted_content=encrypted,
            sha256_hash=str(hash(raw_bytes)),
            status="pending",
        )
        session.add(doc)
        session.commit()
        print(f"  -> Uploaded '{fname}': {desc}")
    print()

    # 4. Run LangGraph Multi-Agent Processing Pipeline
    print("[4/4] Executing LangGraph ProcessingOrchestrator across documents & case...")
    orchestrator = ProcessingOrchestrator(db_session=session, llm_client=demo_llm, embedder=demo_embedder)
    case_results = orchestrator.process_case(case.id)

    # 5. Display Synthesized Intelligence Output
    print("\n" + "=" * 80)
    print("DEMONSTRATION RESULTS & CASE INTELLIGENCE SUMMARY")
    print("=" * 80)

    manager = CaseManager(session)
    dashboard = manager.get_dashboard(case_id=case.id, user_id="demo_user", is_admin=True)

    print(f"Case Title       : {dashboard['title']}")
    print(f"Court Forum      : {dashboard['court']}")
    print(f"Documents Ingested: {dashboard['total_documents']}")
    print(f"Total Facts Found : {dashboard['total_facts']}")
    print(f"Timeline Events   : {dashboard['timeline_events_count']}")
    print(f"Contradictions    : {dashboard['contradictions_count']}")

    print("\n--- CHRONOLOGICAL TIMELINE (Normalized Dates) ---")
    timeline = manager.get_timeline(case_id=case.id, user_id="demo_user", is_admin=True)
    for idx, ev in enumerate(timeline["events"][:5], 1):
        importance = "[HIGH]" if ev["is_important"] else "[NORM]"
        print(f"  {idx}. {ev['date']} {importance} : {ev['title']} - {ev['description'][:80]}...")

    print("\n--- DATABASE-VERIFIED PRECEDENT MATCHES (Hard Rule 4) ---")
    precedents = manager.get_similar_cases(case_id=case.id, user_id="demo_user", is_admin=True)
    if precedents["similar_cases"]:
        for idx, sc in enumerate(precedents["similar_cases"][:3], 1):
            print(f"  {idx}. {sc['title']} ({sc['citation']}) - Score: {sc['score']}")
            print(f"     Holding: {sc['matched_paragraph'][:100]}...")
            print(f"     Why Similar: {sc['why_similar']}")
    else:
        print(f"  {precedents.get('not_found_message', 'No similar precedent above threshold.')}")

    print("\n" + "=" * 80)
    print("MANDATORY DECISION-SUPPORT DISCLAIMER:")
    print(settings.DISCLAIMER_TEXT)
    print("=" * 80 + "\n")

    # Clean up demo SQLite database
    session.close()
    if Path("demo_lexagent.db").exists():
        try:
            Path("demo_lexagent.db").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    run_demo()
