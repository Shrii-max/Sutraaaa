"""Import authorized court JSONL exports. Run periodically using a job scheduler."""

import argparse
from pathlib import Path

from app.db.session import get_db
from app.ingestion.judgments import ingest_judgment_items, load_judgments_from_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("Export directory does not exist")

    files = sorted(args.directory.glob("*.jsonl"))
    if not files:
        print("No JSONL exports available.")
        return

    sessions = get_db()
    session = next(sessions)
    try:
        for path in files:
            items = load_judgments_from_jsonl(path)
            if not items or any(not item.source_url for item in items):
                raise ValueError(f"{path.name}: expected judgment records with source URLs")
            judgments, chunks = ingest_judgment_items(items, session=session)
            print(f"{path.name}: {judgments} judgments, {chunks} chunks")
    finally:
        sessions.close()


if __name__ == "__main__":
    main()
