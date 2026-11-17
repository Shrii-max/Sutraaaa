"""Regression checks for the Moot Court text-mode boundary."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.moot_assessment import PointAssessment, update_leaning, verify_authorities
from app.agents.moot_graph import BenchReply, recent_dialogue
from app.api.routers.moot_court import MootSession, owned, save, transcript
from app.db.models import Judgment, UserModel
from app.db.session import Base


@pytest.fixture
def hearing_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.mark.parametrize("side, expected", [("petitioner", 60), ("respondent", 40)])
def test_leaning_is_side_aware(side, expected):
    point = PointAssessment(
        strength=1, precedent=1, statute=1, factual_consistency=1,
        responsiveness=1, confidence=1,
    )
    assert update_leaning(50, point, side) == pytest.approx(expected)
    assert update_leaning(50, point, side, repeated=True) == 50


@pytest.mark.parametrize("line", [
    "**Answer**", "Point one. Point two.", "2020 SCC 123",
    "Lawyer v. State", 'Justice Rao said "Granted".',
])
def test_rejects_non_spoken_or_authority_text(line):
    with pytest.raises(ValidationError):
        BenchReply(sentences=[line])


def test_accepts_short_hindi_and_hinglish_replies():
    for line in ["आप इस तर्क का आधार बताइए।", "Counsel, इस point का आधार क्या है?"]:
        assert BenchReply(sentences=[line]).sentences == [line]


def test_prior_leaning_does_not_enter_dialogue_prompt():
    assert recent_dialogue({"history": [{
        "text": "My submission", "reply": "Please continue.", "leaning_change": {"current": 60},
    }]}) == [{"lawyer": "My submission", "judge": "Please continue."}]


def test_authority_verification_and_transcript_revocation(hearing_db):
    judgment = Judgment(
        id="authority", title="Test authority", court="Supreme Court", date="2020",
        citation="Test citation", source_url="https://example.test/judgment",
        verification_status="verified", is_overruled=False,
    )
    hearing_db.add(judgment)
    hearing_db.commit()
    assert verify_authorities(hearing_db, ["unknown", "authority", "authority"]) == [judgment]
    row = MootSession(id="hearing", revision=1, state={"status": "open", "history": [{
        "text": "Submission", "reply": "Proceed.", "authorities": [{"id": judgment.id}],
    }]})
    assert transcript(hearing_db, row)["turns"][0]["authorities"] == [{"id": judgment.id}]
    judgment.is_overruled = True
    hearing_db.commit()
    assert transcript(hearing_db, row)["turns"][0]["authorities"] == []


def test_other_user_cannot_fetch_session_and_stale_write_fails(hearing_db):
    row = MootSession(id="hearing", case_id="case", owner_id="owner", state={})
    hearing_db.add(row)
    hearing_db.commit()
    with pytest.raises(HTTPException) as denied:
        owned(hearing_db, UserModel(id="other"), row.id)
    assert denied.value.status_code == 404
    save(hearing_db, row, 0, {"status": "ended"})
    with pytest.raises(HTTPException) as conflict:
        save(hearing_db, row, 0, {"status": "open"})
    assert conflict.value.status_code == 409


def test_transcript_includes_reply_source(hearing_db):
    row_llm = MootSession(id="h1", revision=0, state={"status": "open", "history": [
        {"text": "Sub", "reply": "Rep", "reply_source": "llm", "authorities": []}
    ]})
    assert transcript(hearing_db, row_llm)["turns"][0]["reply_source"] == "llm"

    row_template = MootSession(id="h2", revision=0, state={"status": "open", "history": [
        {"text": "Sub", "reply": "Rep", "authorities": []}
    ]})
    assert transcript(hearing_db, row_template)["turns"][0]["reply_source"] == "template"


