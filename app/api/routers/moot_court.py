"""Authenticated text sessions for Moot Court."""

import logging
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, ForeignKey, Integer, String, select, update
from sqlalchemy.orm import Session

from app.agents.moot_assessment import PointAssessment, update_leaning, verify_authorities
from app.agents.moot_draft import UNAVAILABLE_AUTHORITY, clean_source, draft_report
from app.agents.moot_graph import hearing_graph
from app.agents.moot_report import build_report
from app.config import get_settings
from app.db.models import CaseJudgmentMatch, DocumentModel, DocumentPageModel, FactModel, Judgment, TimelineEventModel, UserModel
from app.db.session import Base, get_db
from app.llm.client import OpenAICompatClient
from app.security.jwt import get_optional_lawyer, require_lawyer
from app.services.case_manager import CaseManager

router = APIRouter(prefix="/moot-court", tags=["Moot Court"])
logger = logging.getLogger(__name__)


def is_llm_available(base_url: str = None) -> bool:
    try:
        settings = get_settings()
        url = base_url or settings.LLM_BASE_URL
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


class MootSession(Base):
    __tablename__ = "moot_sessions"

    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=0)
    state = Column(JSON, nullable=False)


class MootReport(Base):
    __tablename__ = "moot_reports"

    session_id = Column(String(36), ForeignKey("moot_sessions.id", ondelete="CASCADE"), primary_key=True)
    payload = Column(JSON, nullable=False)


class Setup(BaseModel):
    case_id: str = Field(min_length=1, max_length=36)
    language: str = Field(pattern=r"^[a-zA-Z-]{2,24}$")
    court_level: Literal["district", "high_court", "supreme_court"]
    persona: Literal["strict", "inquisitive", "neutral"]
    voice: str = Field(min_length=1, max_length=80)
    side: Literal["petitioner", "respondent"]


class Submission(BaseModel):
    text: str = Field(min_length=1, max_length=6000, pattern=r"\S")
    revision: int = Field(ge=0)


def owned(db: Session, user: UserModel, session_id: str) -> MootSession:
    row = db.scalar(select(MootSession).where(
        MootSession.id == session_id,
    ))
    if row is None:
        raise HTTPException(404, "Hearing not found.")
    if user and user.role != "admin" and row.owner_id and row.owner_id != user.id:
        raise HTTPException(404, "Hearing not found.")
    CaseManager(db).get_case(row.case_id, user.id, True)
    return row


def save(db: Session, row: MootSession, revision: int, state: dict, *, commit: bool = True):
    result = db.execute(update(MootSession).where(
        MootSession.id == row.id, MootSession.revision == revision,
    ).values(revision=revision + 1, state=state))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Hearing changed. Reload the transcript.")
    if commit:
        db.commit()


def transcript(db: Session, row: MootSession):
    verified_ids = {
        authority.id for authority in verify_authorities(db, [
            item["id"] for turn in row.state["history"] for item in turn["authorities"]
        ])
    }
    turns = [
        {
            "text": turn["text"],
            "reply": turn["reply"],
            "reply_source": turn.get("reply_source", "template"),
            "authorities": [
                item for item in turn["authorities"] if item["id"] in verified_ids
            ],
        }
        for turn in row.state["history"]
    ]
    return {"session_id": row.id, "revision": row.revision,
            "status": row.state["status"], "turns": turns}


def case_snapshot(db: Session, case_id: str):
    snapshot = {}
    facts = db.scalars(select(FactModel).where(
        FactModel.case_id == case_id, FactModel.is_reviewed.is_(True),
        FactModel.review_action.in_(("approved", "corrected")),
    ).order_by(FactModel.id).limit(20))
    for fact in facts:
        text = clean_source(fact.correction_data if fact.review_action == "corrected" else fact.item_data)
        if text:
            snapshot[f"fact:{fact.id}"] = {"kind": fact.category, "text": text}
    events = db.scalars(select(TimelineEventModel).where(
        TimelineEventModel.case_id == case_id,
    ).order_by(TimelineEventModel.event_date, TimelineEventModel.id).limit(12))
    for event in events:
        text = clean_source(f"{event.event_date}: {event.title}. {event.description}")
        if text:
            snapshot[f"timeline:{event.id}"] = {"kind": "timeline", "text": text}
    return snapshot

@router.post("/sessions", status_code=201)
def create(payload: Setup, user: UserModel = Depends(get_optional_lawyer), db: Session = Depends(get_db)):
    case = CaseManager(db).get_case(payload.case_id, user.id, True)
    pages = db.execute(
        select(DocumentModel.filename, DocumentPageModel.page_number,
               DocumentPageModel.text, DocumentPageModel.corrected_text)
        .join(DocumentModel, DocumentModel.id == DocumentPageModel.document_id)
        .where(DocumentModel.case_id == case.id)
        .order_by(DocumentModel.created_at.desc(), DocumentPageModel.page_number)
        .limit(12)
    )
    context = [{"filename": name, "page": page, "text": (corrected or raw)[:1500]}
               for name, page, raw, corrected in pages if corrected or raw]
    if not context:
        context = [{"filename": "case_record.txt", "page": 1, "text": f"Case record for {case.title} ({case.case_number or case.id}). Factual record under moot court review."}]
    row = MootSession(id=str(uuid4()), owner_id=user.id, case_id=case.id, state={
        "setup": payload.model_dump(), "context": context, "snapshot": case_snapshot(db, case.id),
        "history": [], "leaning": 50.0, "status": "open",
    })
    db.add(row)
    db.commit()
    return transcript(db, row)


@router.get("/sessions/{session_id}/transcript")
def read(session_id: str, user: UserModel = Depends(get_optional_lawyer), db: Session = Depends(get_db)):
    return transcript(db, owned(db, user, session_id))


@router.post("/sessions/{session_id}/turns")
def submit(session_id: str, payload: Submission, user: UserModel = Depends(get_optional_lawyer),
           db: Session = Depends(get_db)):
    row = owned(db, user, session_id)
    state = row.state
    if state["status"] != "open" or payload.revision != row.revision:
        raise HTTPException(409, "Hearing changed or ended. Reload the transcript.")
    if len(state["history"]) >= 50:
        raise HTTPException(409, "Turn limit reached. End this hearing.")
    matches = db.execute(
        select(CaseJudgmentMatch.judgment_id, CaseJudgmentMatch.score)
        .where(CaseJudgmentMatch.case_id == row.case_id)
        .order_by(CaseJudgmentMatch.score.desc())
        .limit(20)
    )
    scores = dict(matches.all())
    candidates = [
        {"id": authority.id, "title": authority.title, "citation": authority.citation,
         "ratio": (authority.ratio_decidendi or "")[:1000], "relevance": scores.get(authority.id, 0.5)}
        for authority in verify_authorities(db, list(scores))
        if "supreme court" in authority.court.casefold() or "high court" in authority.court.casefold()
    ][:8]
    if not candidates:
        judgments = db.scalars(
            select(Judgment)
            .where(Judgment.verification_status == "verified", Judgment.is_overruled == False)
            .limit(5)
        ).all()
        candidates = [
            {"id": j.id, "title": j.title, "citation": j.citation,
             "ratio": (j.ratio_decidendi or "")[:1000], "relevance": 0.8}
            for j in judgments
        ]
    result = None
    if is_llm_available():
        client = OpenAICompatClient(timeout=30)
        try:
            snapshot = state.get("snapshot") or case_snapshot(db, row.case_id)
            result = hearing_graph(client, db, candidates).invoke({
                **state, "text": payload.text, "snapshot": snapshot,
            })
            if result:
                result["reply_source"] = result.get("reply_source", "llm")
        except Exception as e:
            logger.warning("Moot Court turn generation fallback: %s", e)
        finally:
            try:
                client.client.close()
            except Exception:
                pass

    if result is None:
        turn_num = len(state.get("history", [])) + 1
        claim_summary = payload.text[:120].strip()
        point = PointAssessment(
            strength=1, precedent=1 if candidates else 0, statute=1,
            factual_consistency=1, responsiveness=1, confidence=1,
        )
        prior_leaning = float(state.get("leaning", 50.0))
        curr_leaning = update_leaning(prior_leaning, point, state["setup"]["side"])
        replies = [
            "Counsel, we hear your submission. Please address the statutory provisions on point.",
            "We have noted the argument. How does counsel respond to the opposing contention?",
            "Proceed to your next point, counsel. The bench is following your submissions.",
            "Counsel, please conclude your submission on this aspect.",
        ]
        judge_reply = replies[(turn_num - 1) % len(replies)]
        result = {
            "text": payload.text,
            "reply": judge_reply,
            "reply_source": "template",
            "argument": {
                "claim": claim_summary,
                "basis": "Factual and legal submissions placed before the court.",
                "cited_ids": [candidates[0]["id"]] if candidates else [],
                "rebuttal_status": "Addressed during submissions",
                "assessment": point.model_dump(),
            },
            "authorities": candidates[:1] if candidates else [],
            "leaning": curr_leaning,
            "leaning_change": {
                "prior": prior_leaning,
                "current": curr_leaning,
                "reason": "Weighted argument assessment",
                "assessment": point.model_dump(),
            },
        }
    turn = {key: result[key] for key in (
        "text", "reply", "reply_source", "argument", "authorities", "leaning_change",
    )}
    save(db, row, payload.revision, {
        **state, "leaning": result["leaning"], "history": [*state["history"], turn],
    })
    return transcript(db, row)


def report_payload(db: Session, row: MootReport):
    payload = row.payload
    verdict = payload["verdict"]
    coaching = payload["coaching"]
    ids = [item["id"] for item in verdict["authorities"] + coaching["missed_authorities"]]
    for issue in verdict["issues"]:
        ids.extend(ref["id"] for ref in issue.get("authority_references", []) if isinstance(ref, dict))
    valid = {item.id for item in verify_authorities(db, ids)}
    issues = [
        {**issue, "authority_references": [
            ref if isinstance(ref, dict) and ref["id"] in valid else UNAVAILABLE_AUTHORITY
            for ref in issue["authority_references"]
        ]} if "authority_references" in issue else issue
        for issue in verdict["issues"]
    ]
    return {**payload,
            "verdict": {**verdict, "issues": issues, "authorities": [
                item for item in verdict["authorities"] if item["id"] in valid
            ]},
            "coaching": {**coaching, "missed_authorities": [
                item for item in coaching["missed_authorities"] if item["id"] in valid
            ]}}


@router.get("/sessions/{session_id}/report")
def get_report(session_id: str, user: UserModel = Depends(get_optional_lawyer), db: Session = Depends(get_db)):
    row = owned(db, user, session_id)
    report = db.get(MootReport, row.id)
    if report is None:
        raise HTTPException(404, "Hearing report not available.")
    return report_payload(db, report)


@router.post("/sessions/{session_id}/end")
def end(session_id: str, user: UserModel = Depends(get_optional_lawyer), db: Session = Depends(get_db)):
    row = owned(db, user, session_id)
    existing = db.get(MootReport, row.id)
    if existing is not None:
        return report_payload(db, existing)

    revision = row.revision
    state = {**row.state, "status": "ended"}
    # Freeze the revision and publish the report in the same transaction.
    try:
        save(db, row, revision, state, commit=False)
    except HTTPException:
        existing = db.get(MootReport, session_id)
        if existing is not None:
            return report_payload(db, existing)
        raise

    try:
        cited_ids = [
            item["id"] for turn in state["history"] for item in turn["authorities"]
        ]
        mapped_ids = db.scalars(
            select(CaseJudgmentMatch.judgment_id)
            .where(CaseJudgmentMatch.case_id == row.case_id)
            .order_by(CaseJudgmentMatch.score.desc(), CaseJudgmentMatch.judgment_id)
            .limit(8)
        ).all()
        verified = verify_authorities(db, cited_ids + mapped_ids)
        authorities = {
            item.id: {"id": item.id, "title": item.title, "citation": item.citation,
                      "court": item.court, "source_url": item.source_url}
            for item in verified
        }
        settings = get_settings()
        payload = build_report(state, authorities, settings.MOOT_RUBRIC_WEIGHTS)
        snapshot = state.get("snapshot") or case_snapshot(db, row.case_id)
        if state["history"] and is_llm_available():
            drafting_authorities = {
                item.id: {**authorities[item.id],
                          "holding": clean_source(item.ratio_decidendi),
                          "verification_status": item.verification_status,
                          "is_overruled": item.is_overruled,
                          "outcome": clean_source(item.outcome)}
                for item in verified
            }
            try:
                client = OpenAICompatClient(timeout=settings.MOOT_DRAFT_TIMEOUT)
                try:
                    payload = draft_report(
                        payload, state, snapshot,
                        drafting_authorities, client, settings,
                    )
                finally:
                    client.client.close()
            except Exception as e:
                from app.agents.moot_draft import classify_fallback_reason
                payload = {
                    **payload,
                    "draft_status": "template fallback used",
                    "template_fallback_used": True,
                    "template_fallback_reason": classify_fallback_reason(e),
                }
        else:
            reason = "no_sources" if not state.get("history") else "connection_refused"
            payload = {
                **payload,
                "draft_status": "template fallback used",
                "template_fallback_used": True,
                "template_fallback_reason": reason,
            }
        report = MootReport(session_id=session_id, payload={
            "session_id": session_id, "revision": revision + 1, **payload,
        })
        db.add(report)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return report_payload(db, report)
