"""Standalone HTTP runner for LexAgent Legal Research Service.

Usage:
    python run_server.py [--host 0.0.0.0] [--port 8000]

Can be run independently to expose all Legal Research, Case Intelligence, and Auth REST APIs over HTTP.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default to local SQLite production database if DB_URL / DATABASE_URL not set
LIVE_DB = PROJECT_ROOT / "lexagent.db"
if "DATABASE_URL" not in os.environ and "DB_URL" not in os.environ:
    os.environ["DATABASE_URL"] = f"sqlite:///{LIVE_DB.as_posix()}"
    os.environ["DB_URL"] = f"sqlite:///{LIVE_DB.as_posix()}"

os.environ.setdefault("AUTO_INIT_DB", "true")

import uvicorn
from app.config import get_settings
from app.db.session import init_db, get_session_factory
from app.db.models import Judgment, StatuteSection, UserModel
from app.security.jwt import hash_password


def ensure_seeded_database():
    """Ensure that the local SQLite database exists. Only seed demo users if DEMO_MODE=true."""
    settings = get_settings()
    init_db()

    factory = get_session_factory()
    with factory() as session:
        j_count = session.query(Judgment).count()
        s_count = session.query(StatuteSection).count()

        if s_count == 0 or j_count == 0:
            demo_db_path = PROJECT_ROOT / "demo_lexagent.db"
            if demo_db_path.exists():
                import sqlite3
                src = sqlite3.connect(demo_db_path)
                dst = sqlite3.connect(LIVE_DB)
                for table in ["statute_sections", "judgments", "judgment_chunks"]:
                    cur_src = src.cursor()
                    cur_dst = dst.cursor()
                    cur_src.execute(f"SELECT * FROM {table}")
                    rows = cur_src.fetchall()
                    if rows:
                        cols = [d[0] for d in cur_src.description]
                        placeholders = ",".join(["?"] * len(cols))
                        col_names = ",".join(cols)
                        cur_dst.executemany(f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})", rows)
                        dst.commit()
                src.close()
                dst.close()
                print("[+] Seeded reference Bare-Act Statutes & Landmark Precedents into live database.")

        j_count = session.query(Judgment).count()
        s_count = session.query(StatuteSection).count()
        u_count = session.query(UserModel).count()

        # Seed Sutra advocate user only if DEMO_MODE is true
        if os.environ.get("DEMO_MODE") == "true":
            aditi = session.query(UserModel).filter(UserModel.email == "aditi.khanna@sutra.demo").first()
            if not aditi:
                aditi = UserModel(
                    id="user-sutra-aditi",
                    email="aditi.khanna@sutra.demo",
                    password_hash=hash_password("sutra-demo"),
                    full_name="Aditi Khanna",
                    role="lawyer",
                    is_active=True,
                )
                session.add(aditi)
                session.commit()
                print("[+] DEMO_MODE: Seeded demo Sutra counsel: aditi.khanna@sutra.demo")

        print(f"[*] LexAgent Database Ready: {j_count} Judgments, {s_count} Statutory Provisions, {session.query(UserModel).count()} Users.")


def main():
    parser = argparse.ArgumentParser(description="LexAgent Legal Research HTTP Service")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5986, help="Port to serve (default: 5986)")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn hot reload")
    args = parser.parse_args()

    ensure_seeded_database()

    print("=" * 70)
    print("  LEXAGENT LEGAL RESEARCH SERVICE (HTTP)")
    print(f"  URL: http://localhost:{args.port}")
    print(f"  API Docs: http://localhost:{args.port}/docs")
    print(f"  Research Endpoint: http://localhost:{args.port}/api/v1/research")
    print(f"  Health Check: http://localhost:{args.port}/api/v1/health")
    print("=" * 70)

    uvicorn.run("app.api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
