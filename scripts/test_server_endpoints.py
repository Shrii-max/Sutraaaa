import sys
import time
import threading
import urllib.request
import json
from pathlib import Path

LEXAGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LEXAGENT_DIR))

import uvicorn
from app.api.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=5986, log_level="warning")

def probe():
    time.sleep(2)
    urls = [
        ("Root / UI", "http://127.0.0.1:5986/"),
        ("Health API", "http://127.0.0.1:5986/api/v1/health"),
        ("Docs (OpenAPI)", "http://127.0.0.1:5986/docs"),
        ("Cases API (Protected)", "http://127.0.0.1:5986/api/v1/cases"),
    ]
    
    print("=" * 60)
    print("  PROBING LEXAGENT UNIFIED SERVER ON PORT 5986")
    print("=" * 60)
    
    for label, url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ProbeClient"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                print(f"[+] {label:<25} -> Status: {resp.status} | Bytes: {len(data)}")
                if label == "Health API":
                    print(f"    Health Payload: {data.decode()[:200]}")
                elif label == "Bare Act / Statute Search":
                    parsed = json.loads(data.decode())
                    print(f"    Statute Results Count: {len(parsed.get('results', []))}")
                    if parsed.get('results'):
                        sec = parsed['results'][0]
                        print(f"    First Result: Section {sec.get('section_number')} ({sec.get('act_name')})")
                        print(f"    Verification Status: {sec.get('verification_status', 'N/A')} | Source URL: {sec.get('source_url')}")
        except Exception as e:
            print(f"[-] {label:<25} -> Error: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    probe()
    print("=" * 60)
    print("PROBE COMPLETED SUCCESSFULLY.")
    sys.exit(0)
