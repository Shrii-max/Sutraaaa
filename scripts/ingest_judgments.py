"""CLI script to ingest legal judgments from JSONL files into the LexAgent vector and full-text database.

Usage:
    python -m scripts.ingest_judgments --input tests/fixtures/sample_judgments.jsonl
    python -m scripts.ingest_judgments --input path/to/judgments.jsonl --batch-size 32
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import get_db, init_db
from app.ingestion.judgments import load_judgments_from_jsonl, ingest_judgment_items
from app.llm.client import LocalEmbeddingClient


def main():
    parser = argparse.ArgumentParser(description="LexAgent Judgment Ingestion Pipeline")
    parser.add_argument("--input", "-i", required=True, help="Path to input judgments JSONL file")
    parser.add_argument("--batch-size", "-b", type=int, default=16, help="Embedding batch size (default 16)")
    parser.add_argument("--db-url", help="Optional override for database URL (e.g. sqlite:///test.db)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.stderr.write(f"Error: Input file '{args.input}' does not exist.\n")
        sys.exit(1)

    print(f"Loading judgments from '{input_path}'...")
    try:
        items = load_judgments_from_jsonl(input_path)
        print(f"Parsed {len(items)} judgment records.")

        if not items:
            print("No valid records found to ingest.")
            return

        if args.db_url:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from app.db.session import Base
            engine = create_engine(args.db_url)
            Base.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
        else:
            db_gen = get_db()
            session = next(db_gen)

        embedder = LocalEmbeddingClient()
        num_judgments, num_chunks = ingest_judgment_items(
            items=items,
            session=session,
            embedder=embedder,
            batch_size=args.batch_size,
        )

        print(f"Successfully upserted {num_judgments} judgments with {num_chunks} paragraph chunks into database.")

    except Exception as e:
        sys.stderr.write(f"Ingestion failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
