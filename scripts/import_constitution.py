"""Import the official Constitution PDF into a local page archive for source lookup."""

import argparse
import hashlib
import sqlite3
from pathlib import Path

import pymupdf

SOURCE = "https://www.legislative.gov.in/static/uploads/2025/08/b9a933fb88c0a5afba254256bc55a3f0.pdf"


def import_pdf(pdf: Path, database: Path) -> int:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    with pymupdf.open(pdf) as document:
        pages = [
            (digest, page.number + 1, page.get_text(), SOURCE)
            for page in document
        ]
    if not pages or not any(text.strip() for _, _, text, _ in pages):
        raise ValueError("No extractable PDF text")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS constitution_pages (
                sha256 TEXT NOT NULL, pdf_page INTEGER NOT NULL,
                text TEXT NOT NULL, source_url TEXT NOT NULL,
                PRIMARY KEY (sha256, pdf_page)
            )"""
        )
        connection.executemany(
            "INSERT OR IGNORE INTO constitution_pages VALUES (?, ?, ?, ?)", pages
        )
    return len(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=Path("app/data/constitution-india-2026.pdf"))
    parser.add_argument("--db", type=Path, default=Path("app/data/legal_sources.sqlite3"))
    args = parser.parse_args()
    print(f"Imported {import_pdf(args.pdf, args.db)} Constitution PDF pages")


if __name__ == "__main__":
    main()
