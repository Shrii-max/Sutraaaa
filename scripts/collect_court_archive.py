"""Collect bounded batches from the public Indian court archives."""

import argparse
import json
import re
import uuid
from html import unescape
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

import httpx
import pymupdf
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Judgment
from app.db.session import Base, get_db
from app.ingestion.judgments import JudgmentIngestItem, ingest_judgment_items


def field(html: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*:</span><font[^>]*>(.*?)</font>", html, re.I | re.S)
    return unescape(match[1]).strip() if match else None


def collect(client: httpx.Client, session: Session, court: str, year: int, limit: int, refresh_metadata: bool = False, *, keywords: tuple[str, ...] = (), max_entries: int | None = None) -> int:
    bucket = f"https://indian-{court}-court-judgments.s3.ap-south-1.amazonaws.com/"
    prefix = f"metadata/json/year={year}/"
    parameters = {"list-type": 2, "prefix": prefix, "max-keys": 100}
    imported = 0
    failures = 0
    inspected = 0
    while imported < limit:
        response = client.get(bucket + "?" + urlencode(parameters))
        response.raise_for_status()
        listing = ElementTree.fromstring(response.content)
        for element in listing.findall("{*}Contents"):
            key = element.findtext("{*}Key", "")
            if not key.endswith(".json"):
                continue
            if max_entries is not None and inspected >= max_entries:
                return imported
            inspected += 1
            identity = str(uuid.uuid5(uuid.NAMESPACE_URL, bucket + key))
            existing = session.get(Judgment, identity)
            if existing is not None and (existing.summary or not refresh_metadata):
                continue
            try:
                response = client.get(bucket + quote(key, safe="/="))
                response.raise_for_status()
                metadata = response.json()
                html = metadata["raw_html"]
                title = re.search(r'aria-label="([^"]+) pdf"', html, re.I)
                date = field(html, "Decision Date")
                outcome = field(html, "Disposal Nature")
                if not title or not date or not outcome:
                    continue
                issue = re.search(
                    r"""Issue for Consideration\s+(.*?)<br>\s*<strong class=['"]caseDetailsTD""",
                    html, re.I | re.S,
                )
                searchable = unescape(re.sub(r"<[^>]+>", " ", f"{title[1]} {issue[1] if issue else ''}")).casefold()
                if keywords and not any(re.search(r"\b" + re.escape(word) + r"\b", searchable) for word in keywords):
                    continue
                stem = key[:-5].removeprefix(prefix)
                if court == "supreme":
                    pdf_key = f"data/pdf/year={year}/english/{stem}_EN.pdf"
                else:
                    pdf_key = f"data/pdf/year={year}/{stem}.pdf"
                url = bucket + quote(pdf_key, safe="/=")
                response = client.get(url)
                response.raise_for_status()
                with pymupdf.open(stream=response.content, filetype="pdf") as pdf:
                    text = "\n\n".join(page.get_text() for page in pdf).strip()
                if len(text) < 15:
                    continue
                citation = metadata.get("nc_display") or f"{court.upper()} archive {stem}"
                bench = field(html, "Bench")
                item = JudgmentIngestItem(
                    id=identity, title=unescape(title[1]).strip(),
                    court=metadata.get("court_name") or "Supreme Court of India",
                    date=date, citation=citation, outcome=outcome, source_url=url, full_text=text,
                    bench=bench,
                    summary=unescape(re.sub(r"<[^>]+>", "", issue[1])).strip() if issue else None,
                )
                count, _ = ingest_judgment_items([item], session=session)
                imported += count
                if imported >= limit:
                    break
            except (httpx.HTTPError, ValueError, KeyError, pymupdf.FileDataError) as exc:
                session.rollback()
                failures += 1
                print(f"Skipped {key}: {exc}")
                if failures >= limit:
                    raise RuntimeError("Court archive batch reached its error limit") from exc
        token = listing.findtext("{*}NextContinuationToken")
        if not token:
            break
        parameters["continuation-token"] = token
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--court", choices=("supreme", "high"), required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--refresh-metadata", action="store_true")
    parser.add_argument("--db-url", help="Override database for a local smoke test")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.db_url:
        engine = create_engine(args.db_url)
        Base.metadata.create_all(engine)
        with Session(engine) as session, httpx.Client(timeout=30) as client:
            print(f"Imported {collect(client, session, args.court, args.year, args.limit, args.refresh_metadata)} judgments")
    else:
        sessions = get_db()
        try:
            with httpx.Client(timeout=30) as client:
                print(f"Imported {collect(client, next(sessions), args.court, args.year, args.limit, args.refresh_metadata)} judgments")
        finally:
            sessions.close()


if __name__ == "__main__":
    main()
