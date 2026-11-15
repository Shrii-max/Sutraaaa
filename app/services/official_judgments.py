"""Match private case terms locally against the Supreme Court's public summaries."""

import json
import math
from collections import Counter, defaultdict
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

def cited_sections(text: str) -> set[tuple[str, str]]:
    """Extract explicit act and section combinations without equating section numbers across acts."""
    acts = {
        "ipc": r"ipc|indian penal code", "crpc": r"crpc|code of criminal procedure",
        "bns": r"bns|bharatiya nyaya sanhita", "bnss": r"bnss|bharatiya nagarik suraksha sanhita",
        "ni act": r"ni act|negotiable instruments act",
        "contract act": r"(?:indian )?contract act",
    }
    text = re.sub(r"\s+", " ", text.casefold())
    return {(code, section) for code, alias in acts.items() for section in re.findall(
        rf"\b(?:section|sec\.?)\s*(\d+[a-z]?)\s+(?:(?:of\s+)?the\s+|of\s+)?(?:{alias})\b",
        text,
    )}


def payment_dispute_topic(text: str) -> bool:
    """Detect a supply invoice dispute using corroborating terms, including inflections."""
    normalized = re.sub(r"\s+", " ", text.casefold())
    return all(re.search(pattern, normalized) for pattern in (
        r"\b(?:supply|suppl(?:ied|ying)|delivery|delivered|shipment)\b",
        r"\binvoices?\b",
        r"\b(?:unpaid|outstanding|non.payment|did not (?:pay|make)|failed to pay)\b",
    ))


def rank_document_judgments(db: Session, document_id: str) -> list[dict]:
    """Rank stored public judgments against one document without external calls."""
    pages = db.scalars(select(DocumentPageModel.text).where(
        DocumentPageModel.document_id == document_id,
    ).order_by(DocumentPageModel.page_number)).all()
    source = " ".join(text for text in pages if text)
    if not source.strip():
        return []
    generic = {
        "allowed", "appellant", "argued", "cannot", "counsel", "dismissed", "filed",
        "given", "held", "learned", "mentioned", "present", "record", "respondent",
        "submitted", "therefore", "understand", "years",
    }
    terms = keywords(source) - generic
    counts = Counter(re.findall(r"[^\W\d_]{4,}", source.casefold()))
    citations = {(year, number) for year, number in re.findall(r"\b(\d{4})\s+INSC\s+(\d+)\b", source, re.I)}

    source_sections = cited_sections(source)
    source_payment_dispute = payment_dispute_topic(source)
    public_hosts = {"api.sci.gov.in", "www.sci.gov.in", "indian-supreme-court-judgments.s3.ap-south-1.amazonaws.com"}
    judgments = [judgment for judgment in db.scalars(select(Judgment).order_by(Judgment.id))
                 if urlsplit(judgment.source_url or "").hostname in public_hosts]
    descriptions = {judgment.id: keywords(f"{judgment.title} {judgment.summary or ''}") - generic
                    for judgment in judgments}
    rows = db.execute(select(JudgmentChunk.judgment_id, JudgmentChunk.text)
                      .where(JudgmentChunk.judgment_id.in_([judgment.id for judgment in judgments]))).all()
    chunks = defaultdict(list)
    index_terms = {judgment.id: set(descriptions[judgment.id]) for judgment in judgments}
    for judgment_id, text in rows:
        chunk_terms = keywords(text) - generic
        chunks[judgment_id].append((text, chunk_terms))
        index_terms.setdefault(judgment_id, set()).update(chunk_terms)
    frequencies = Counter(term for words in index_terms.values() for term in words)
    weights = {term: math.log((len(judgments) + 1) / (frequencies[term] + 1)) + 1.0
               for term in terms if frequencies[term]}
    important = sorted(weights, key=lambda word: (-weights[word] * math.log1p(counts[word]), word))[:45]
    selected = set(important)
    ranked = []

    for judgment in judgments:
        cited = re.fullmatch(r"(\d{4})\s+INSC\s+(\d+)", judgment.citation, re.I)
        exact = bool(cited and cited.groups() in citations)
        fiscal_title = re.search(r"\b(?:central excise|income tax|customs|goods and services tax)\b",
                                 judgment.title, re.I)
        fiscal_source = re.search(r"\b(?:central excise|income tax|customs|goods and services tax|gst)\b", source, re.I)
        if fiscal_title and not (exact or fiscal_source):
            continue
        shared_sections = source_sections & cited_sections(judgment.full_text or "")
        shared_payment_issue = source_payment_dispute and payment_dispute_topic(judgment.summary or "")
        title_overlap = descriptions[judgment.id] & selected
        candidates = chunks[judgment.id]
        best_text, best_terms = max(candidates, key=lambda chunk: sum(weights.get(word, 0.0)
                                    for word in chunk[1] & selected), default=("", set()))
        overlap = (best_terms & selected) | title_overlap
        # Require topical corroboration. Words confined to unrelated judgment paragraphs carry less weight.
        if not exact and not shared_sections and not shared_payment_issue and (len(overlap) < 3 or (len(title_overlap) < 2 and len(overlap) < 6)):
            continue
        score = 1.0 if exact else min(0.95, (
            1.8 * sum(weights[word] for word in title_overlap) +
            sum(weights[word] for word in best_terms & selected)) / max(sum(weights[word] for word in selected), 1.0))
        if not exact and shared_sections:
            score = min(0.95, max(score, 0.22) + 0.06)
        if not exact and shared_payment_issue:
            score = min(0.95, max(score, 0.22) + 0.09)
        if not exact and score < 0.16:
            continue
        ranked.append({
            "case_id": judgment.id, "title": judgment.title, "court": judgment.court,
            "date": judgment.date, "citation": judgment.citation, "bench": judgment.bench,
            "source_url": judgment.source_url, "score": score,
            "sections_overlap": [f"{act.upper()} §{section}" for act, section in sorted(shared_sections)],
            "decision": judgment.outcome or judgment.summary, "matched_paragraph": best_text[:2500],
            "matched_terms": sorted(overlap, key=lambda word: (-weights[word], word))[:8],
            "match_basis": "Citation in uploaded document" if exact else ("Shared statutory provision" if shared_sections else "Supply and unpaid invoice dispute" if shared_payment_issue else "Shared legal terms"),
            "official_summary": bool(judgment.license_note and judgment.license_note.startswith("Official SCI")),
            "verification_status": judgment.verification_status,
        })
    return sorted(ranked, key=lambda item: (-item["score"], item["citation"]))[:8]
