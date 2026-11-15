"""Data Quality and Repository Health Audit CLI.

Follows v2 Reliability Requirement 5:
`python -m scripts.data_quality_report`:
Inspects judgments, chunks, quarantine count, concordance map coverage, prints report.
"""

import sys
import argparse
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.db.session import get_session_factory, Base
from app.db.models import Judgment, JudgmentChunk, StatuteSection, IngestionQuarantineModel
from app.ingestion.concordance import get_concordance


def generate_data_quality_report(db_url: str = None) -> int:
    concordance = get_concordance()
    concordance_valid, concordance_errors = concordance.validate_mappings()

    print("\n================================================================================")
    print("LEXAGENT DATABASE & STATUTORY KNOWLEDGE HEALTH REPORT")
    print("================================================================================\n")

    settings = get_settings()
    session = None
    target_db = db_url or settings.DB_URL

    try:
        engine = create_engine(target_db, connect_args={"connect_timeout": 2} if "postgresql" in target_db else {})
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        # Probe connection
        session.scalar(select(1))
    except Exception:
        # Fall back to local SQLite demo database if PostgreSQL is not active
        fallback_db = "sqlite:///demo_lexagent.db"
        print(f"Notice: Primary DB at {target_db} unreachable. Auditing {fallback_db}...")
        engine = create_engine(fallback_db)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

    try:
        judgments_count = session.scalar(select(func.count(Judgment.id))) or 0
        chunks_count = session.scalar(select(func.count(JudgmentChunk.id))) or 0
        statutes_count = session.scalar(select(func.count(StatuteSection.id))) or 0
        quarantine_count = session.scalar(select(func.count(IngestionQuarantineModel.id))) or 0
        overruled_count = session.scalar(select(func.count(Judgment.id)).where(Judgment.is_overruled == True)) or 0

        # Recent quarantine records
        recent_quarantines = session.scalars(
            select(IngestionQuarantineModel).order_by(IngestionQuarantineModel.created_at.desc()).limit(5)
        ).all()

        print(f"--- KNOWLEDGE REPOSITORY INVENTORY ---")
        print(f"Total Landmark Judgments Ingested : {judgments_count}")
        print(f"Total Paragraph Embedding Chunks  : {chunks_count}")
        print(f"Total Bare Act Sections Ingested  : {statutes_count}")
        print(f"Overruled Precedents Flagged      : {overruled_count}")
        print(f"Quarantined Records (Bad Data)    : {quarantine_count}")

        print(f"\n--- STATUTORY CONCORDANCE MAPPINGS (IPC-BNS, CrPC-BNSS) ---")
        print(f"Concordance Integrity Valid       : {'YES [PASS]' if concordance_valid else 'NO [FAIL]'}")
        print(f"IPC -> BNS Concordance Mappings   : {len(concordance.ipc_to_bns)} sections")
        print(f"CrPC -> BNSS Concordance Mappings : {len(concordance.crpc_to_bnss)} sections")

        if concordance_errors:
            print("\n[!] Concordance Mapping Issues:")
            for err in concordance_errors:
                print(f"    - {err}")

        if recent_quarantines:
            print("\n--- RECENT QUARANTINED RECORDS SAMPLE ---")
            for q in recent_quarantines:
                print(f"    ID: {q.id} | Type: {q.record_type} | Errors: {q.validation_errors}")

        print("\n================================================================================")
        print("DATA QUALITY AUDIT COMPLETE")
        print("================================================================================\n")

        return 0 if concordance_valid else 1
    except Exception as e:
        print(f"\n[!] Error generating quality report: {e}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(generate_data_quality_report())
