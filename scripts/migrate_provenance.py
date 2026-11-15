"""Migration script to ensure judgments and statute_sections have provenance columns.

Adds:
- source_url, retrieved_on, verified_by, verification_status
Defaults verification_status to 'unverified'.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone

LEXAGENT_DIR = Path(__file__).resolve().parent.parent

def migrate_db(db_path: Path):
    if not db_path.exists():
        print(f"[*] Database {db_path.name} does not exist yet.")
        return

    print(f"[*] Migrating provenance columns on {db_path.name}...")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Check judgments columns
    cur.execute("PRAGMA table_info(judgments)")
    cols = [row[1] for row in cur.fetchall()]
    if "source_url" not in cols:
        cur.execute("ALTER TABLE judgments ADD COLUMN source_url VARCHAR(512)")
        print(f"  + Added source_url to judgments in {db_path.name}")
    if "retrieved_on" not in cols:
        cur.execute("ALTER TABLE judgments ADD COLUMN retrieved_on TIMESTAMP")
        print(f"  + Added retrieved_on to judgments in {db_path.name}")
    if "verified_by" not in cols:
        cur.execute("ALTER TABLE judgments ADD COLUMN verified_by VARCHAR(100)")
        print(f"  + Added verified_by to judgments in {db_path.name}")
    if "verification_status" not in cols:
        cur.execute("ALTER TABLE judgments ADD COLUMN verification_status VARCHAR(50) DEFAULT 'unverified'")
        print(f"  + Added verification_status to judgments in {db_path.name}")

    # Check statute_sections columns
    cur.execute("PRAGMA table_info(statute_sections)")
    s_cols = [row[1] for row in cur.fetchall()]
    if "source_url" not in s_cols:
        cur.execute("ALTER TABLE statute_sections ADD COLUMN source_url VARCHAR(512)")
        print(f"  + Added source_url to statute_sections in {db_path.name}")
    if "retrieved_on" not in s_cols:
        cur.execute("ALTER TABLE statute_sections ADD COLUMN retrieved_on TIMESTAMP")
        print(f"  + Added retrieved_on to statute_sections in {db_path.name}")
    if "verified_by" not in s_cols:
        cur.execute("ALTER TABLE statute_sections ADD COLUMN verified_by VARCHAR(100)")
        print(f"  + Added verified_by to statute_sections in {db_path.name}")
    if "verification_status" not in s_cols:
        cur.execute("ALTER TABLE statute_sections ADD COLUMN verification_status VARCHAR(50) DEFAULT 'unverified'")
        print(f"  + Added verification_status to statute_sections in {db_path.name}")

    # Set provenance defaults for pre-seeded records
    now_iso = datetime.now(timezone.utc).isoformat()

    # Update judgments
    judgment_sources = {
        "(2014) 10 SCC 473": "https://indiankanoon.org/doc/106676356/",
        "(2020) 7 SCC 1": "https://indiankanoon.org/doc/174426572/",
        "(2021) 2 SCC 1": "https://indiankanoon.org/doc/135084931/",
        "(2014) 9 SCC 129": "https://indiankanoon.org/doc/184131566/",
        "(2020) 15 SCC 1": "https://indiankanoon.org/doc/171587327/",
    }
    for cit, url in judgment_sources.items():
        cur.execute(
            "UPDATE judgments SET source_url = ?, retrieved_on = ?, verification_status = 'unverified' WHERE citation = ?",
            (url, now_iso, cit),
        )

    # Update statute_sections
    statute_sources = {
        "420": "https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_00037_186045_1523266765688&sectionId=46200",
        "406": "https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_00037_186045_1523266765688&sectionId=46186",
        "138": "https://www.indiacode.nic.in/show-data?actid=AC_CEN_2_10_00006_188126_1523268870198&sectionId=42138",
        "156": "https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_000010_197402_1517807320555&sectionId=34656",
    }
    for sec_no, url in statute_sources.items():
        cur.execute(
            "UPDATE statute_sections SET source_url = ?, retrieved_on = ?, verification_status = 'unverified' WHERE section_no = ?",
            (url, now_iso, sec_no),
        )

    cur.execute("UPDATE judgments SET verification_status = 'unverified' WHERE verification_status IS NULL")
    cur.execute("UPDATE statute_sections SET verification_status = 'unverified' WHERE verification_status IS NULL")

    con.commit()
    con.close()
    print(f"[+] Successfully migrated provenance columns on {db_path.name}")


if __name__ == "__main__":
    migrate_db(LEXAGENT_DIR / "demo_lexagent.db")
    migrate_db(LEXAGENT_DIR / "lexagent.db")
