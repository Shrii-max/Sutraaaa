"""Exact article reference lookup over the local Constitution PDF archive."""

from pathlib import Path
import re
import sqlite3

from app.schemas.research import ResearchCitation

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "legal_sources.sqlite3"
ARTICLE_QUERY = re.compile(r"\b(?:article|art\.?)\s+(\d{1,3}[A-Za-z]{0,2})\b", re.I)


def lookup_articles(query: str, limit: int, archive: Path = ARCHIVE) -> list[ResearchCitation]:
    article_numbers = dict.fromkeys(match.upper() for match in ARTICLE_QUERY.findall(query))
    if not article_numbers or not archive.is_file():
        return []

    with sqlite3.connect(archive.resolve().as_uri() + "?mode=ro", uri=True) as db:
        edition = db.execute(
            "SELECT sha256 FROM constitution_pages ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if edition is None:
            return []
        pages = db.execute(
            "SELECT pdf_page, text, source_url FROM constitution_pages WHERE sha256 = ? "
            "AND pdf_page > 30 ORDER BY pdf_page",
            edition,
        ).fetchall()

    results = []
    for article in article_numbers:
        heading = re.compile(rf"^\s*{article}\.\s+[A-Z]", re.M)
        for page, text, source in pages:
            match = heading.search(text)
            if match is None:
                continue
            excerpt = text[match.start():].strip()
            results.append(ResearchCitation(
                source_type="constitution",
                id=f"{edition[0]}:{page}:{article}",
                title_or_act="Constitution of India",
                citation_or_section=f"Article {article}",
                verbatim_snippet=excerpt,
                source_url=f"{source}#page={page}",
                pdf_page=page,
            ))
            break
        if len(results) >= limit:
            break
    return results
