"""Match private case terms locally against the Supreme Court's public summaries."""

import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseJudgmentMatch, DocumentModel, DocumentPageModel, Judgment, JudgmentChunk
from app.ingestion.judgments import chunk_judgment_text

INDEX_URL = "https://www.sci.gov.in/landmark-judgment-summaries/"
STOP_WORDS = {
    "about", "after", "against", "appeal", "application", "before", "case", "court",
    "decision", "document", "documents", "following", "high", "india", "judgment",
    "judgments", "law", "legal", "matter", "order", "party", "parties", "proceeding",
    "section", "should", "supreme", "that", "their", "there", "these", "this", "under",
    "were", "what", "when", "where", "whether", "which", "will", "with", "would",
}


def plain(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def keywords(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]{4,}", text.casefold())) - STOP_WORDS


def scan_official_index(html: str):
    """Extract only entries with a citation, bench, decision and an official judgment link."""
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
        if len(cells) < 5:
            continue
        content = cells[4]
        citation = re.search(r"\b(\d{4}\s+INSC\s+\d+)\b", plain(content), re.I)
        title = re.search(r'<span id="causeTitle\d+">(.*?)</span>', content, re.I | re.S)
        links = (unescape(value) for value in re.findall(r"""href=["']([^"']+)""", row, re.I))
        link = next((value for value in links if urlsplit(value).scheme == "https"
                     and urlsplit(value).netloc == "www.sci.gov.in"
                     and urlsplit(value).path == "/view-pdf/"), None)
        text = plain(content)
        bench = re.search(r"Justices:\s*(.*?)\s*Question\(s\):", text, re.I)
        question = re.search(r"Question\(s\):\s*(.*?)\s*Factual Background:", text, re.I)
        decision = re.search(r"Decision of the Supreme Court:\s*(.*?)\s*Reasons for the Decision:", text, re.I)
        if not all((citation, title, link, bench, decision)):
            continue
        try:
            date = datetime.strptime(plain(cells[1]), "%d-%m-%Y").date().isoformat()
        except ValueError:
            continue
        yield {
            "title": plain(title[1]), "citation": citation[1], "date": date, "source_url": link,
            "bench": bench[1], "summary": decision[1], "full_text": text,
            "topic": plain(cells[3]) + " " + (question[1] if question else ""),
        }


def search_and_save(db: Session, case_id: str, topic: str = "") -> int:
    if not topic.strip():
        pages = db.scalars(select(DocumentPageModel.text).join(
            DocumentModel, DocumentModel.id == DocumentPageModel.document_id,
        ).where(DocumentModel.case_id == case_id)
          .order_by(DocumentModel.created_at.desc(), DocumentPageModel.page_number).limit(20)).all()
        topic = " ".join((page or "")[:3000] for page in pages)
    terms = keywords(topic)
    if not terms:
        return 0

    # The same public URL is fetched for every case. Case text and topics stay local.
    with httpx.Client(timeout=12.0, follow_redirects=False) as client:
        response = client.get(INDEX_URL)
        response.raise_for_status()
    entries = list(scan_official_index(response.text))
    if not entries:
        raise ValueError("Supreme Court summary index returned no readable records.")

    ranked = []
    for entry in entries:
        reference = keywords(entry["topic"])
        overlap = terms & reference
        if entry["citation"].replace(" ", "").lower() in re.sub(r"\s+", "", topic.lower()):
            score = 1.0
        elif len(overlap) >= 2 and len(overlap) / max(len(reference), 1) >= 0.15:
            score = min(0.95, len(overlap) / len(reference))
        else:
            continue
        ranked.append((score, overlap, entry))

    for score, overlap, entry in sorted(ranked, key=lambda item: (-item[0], item[2]["citation"]))[:5]:
        judgment = db.scalar(select(Judgment).where(Judgment.citation == entry["citation"]))
        if judgment is None:
            judgment = Judgment(citation=entry["citation"], court="Supreme Court of India")
            db.add(judgment)
        judgment.title = entry["title"][:255]
        judgment.date = entry["date"]
        judgment.bench = entry["bench"][:255]
        judgment.source_url = entry["source_url"]
        judgment.retrieved_on = datetime.now(timezone.utc)
        judgment.summary = entry["summary"]
        if judgment.full_text is None:
            judgment.full_text = entry["full_text"]
            judgment.license_note = "Official SCI editorial summary. Refer to the linked judgment for the controlling text."
            db.flush()
            for index, chunk in enumerate(chunk_judgment_text(entry["full_text"])):
                db.add(JudgmentChunk(judgment_id=judgment.id, chunk_index=index, text=chunk))
        else:
            db.flush()
        link = db.get(CaseJudgmentMatch, (case_id, judgment.id))
        if link is None:
            db.add(CaseJudgmentMatch(case_id=case_id, judgment_id=judgment.id,
                                    score=score, matched_terms=json.dumps(sorted(overlap))))
        else:
            link.score = score
            link.matched_terms = json.dumps(sorted(overlap))

    db.commit()
    return min(len(ranked), 5)
