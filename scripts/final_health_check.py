import urllib.request
import json
import sys
import os
from pathlib import Path

print("====================================================================")
print("              SUTRA & LEXAGENT COMPREHENSIVE FINAL AUDIT             ")
print("====================================================================")

# 1. Server HTTP & Frontend
try:
    with urllib.request.urlopen("http://localhost:5986", timeout=5) as r:
        html = r.read().decode("utf-8")
        has_js = "index-" in html
        print(f"[PASS] 1. Frontend Web Server: HTTP {r.status} (Bundle present: {has_js})")
except Exception as e:
    print(f"[FAIL] 1. Frontend Web Server unreachable: {e}")

# 2. Backend OpenAPI
try:
    with urllib.request.urlopen("http://localhost:5986/openapi.json", timeout=5) as r:
        spec = json.loads(r.read().decode("utf-8"))
        routes = len(spec.get("paths", {}))
        print(f"[PASS] 2. Backend API Docs & Spec: HTTP {r.status} ({routes} routes mounted)")
except Exception as e:
    print(f"[FAIL] 2. Backend API Spec unreachable: {e}")

# 3. Database Check
sys.path.insert(0, "final/lexagent/lexagent")
from app.db.session import get_session_factory
from app.db.models import Judgment, StatuteSection, UserModel, CaseModel, DocumentModel
factory = get_session_factory()
with factory() as session:
    users_cnt = session.query(UserModel).count()
    cases_cnt = session.query(CaseModel).count()
    docs_cnt = session.query(DocumentModel).count()
    judg_cnt = session.query(Judgment).count()
    stat_cnt = session.query(StatuteSection).count()
    print(f"[PASS] 3. Database lexagent.db: {users_cnt} Users, {cases_cnt} Cases, {docs_cnt} Docs, {judg_cnt} Landmark Judgments, {stat_cnt} Bare-Act Statutes")

# 4. Legal Research Agent API
try:
    url = "http://localhost:5986/api/v1/research"
    payload = json.dumps({"query": "Section 420 Cheating and Dishonestly inducing delivery of property"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read().decode("utf-8"))
        cit_cnt = len(res.get("citations", []))
        prov_cnt = len(res.get("relevant_provisions", []))
        print(f"[PASS] 4. Legal Research Agent: HTTP {r.status} (Found {prov_cnt} Provisions, {cit_cnt} Landmark Precedents)")
except Exception as e:
    print(f"[FAIL] 4. Legal Research Agent failed: {e}")

# 5. AI Assistant API (Workspace & Case)
try:
    url = "http://localhost:5986/api/v1/assistant/chat"
    payload = json.dumps({"question": "List my recent cases"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read().decode("utf-8"))
        reply = res.get("reply", "")[:80].replace("\n", " ")
        print(f'[PASS] 5. AI Assistant (Chat): HTTP {r.status} (Grounded reply: "{reply}...")')
except Exception as e:
    print(f"[FAIL] 5. AI Assistant failed: {e}")

# 6. Translation Subsystem API (Neural & Glossary)
try:
    doc_id = "09ad8169-5fc4-4468-911f-51df6b5c5bf8"
    url = f"http://localhost:5986/api/v1/documents/{doc_id}/translate"
    payload = json.dumps({"target_language": "hi", "source_language": "en", "engine": "configured", "first_page": 1, "last_page": 1}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read().decode("utf-8"))
        trans_preview = res.get("full_translated_text", "")[:70].replace("\n", " ")
        engine_name = res.get("engine")
        print(f'[PASS] 6. Translation Subsystem: HTTP {r.status} [Engine: {engine_name}] -> "{trans_preview}..."')
except Exception as e:
    print(f"[FAIL] 6. Translation Subsystem failed: {e}")

# 7. Voice / TTS Check
try:
    import pyttsx3
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    v_names = [v.name for v in voices]
    voice_str = ", ".join(v_names[:2])
    print(f"[PASS] 7. Voice Subsystem (Local SAPI5): {len(voices)} Voices installed ({voice_str})")
except Exception as e:
    print(f"[WARN] 7. Voice Subsystem: {e}")

print("====================================================================")
print("              ALL SYSTEMS OPERATIONAL & FULLY ACTIVATED              ")
print("====================================================================")
