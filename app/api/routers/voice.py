"""Voice router for LexAgent Voice Delivery (Phase C).

Endpoints:
  POST /cases/{id}/voice/brief
  POST /cases/{id}/voice/ask
  GET  /cases/{id}/voice/briefs
"""

import base64
import json
import logging
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import (
    CaseModel,
    DocumentTranslationModel,
    SummaryModel,
    TimelineEventModel,
    UserModel,
    VoiceBriefModel,
)
from app.security.jwt import require_lawyer
from app.schemas.voice import (
    VoiceBriefInput,
    VoiceBriefOutput,
    VoiceQuestionInput,
    VoiceQuestionOutput,
)
from app.agents.voice_brief import VoiceBriefAgent, VoiceQAAgent
from app.voice.gateway import get_voice_gateway
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/cases", tags=["Voice Delivery"])


def _verify_case_access(case: CaseModel, user: UserModel) -> None:
    """Enforce strict tenant isolation on voice operations."""
    if user.role != "admin" and case.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have permission to access case '{case.id}'.",
        )


@router.post("/{id}/voice/brief", response_model=VoiceBriefOutput)
def create_or_play_voice_brief(
    id: str,
    payload: VoiceBriefInput,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Generate spoken legal case brief and synthesize audio via VoiceFlow."""
    case = db.scalar(select(CaseModel).where(CaseModel.id == id))
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{id}' not found.")
    _verify_case_access(case, current_user)

    # Fetch latest summary
    summary_record = db.scalars(
        select(SummaryModel).where(SummaryModel.case_id == id).order_by(SummaryModel.created_at.desc())
    ).first()
    summary_text = summary_record.summary_text if summary_record else "No summary on record."

    # Fetch important timeline events
    events = list(
        db.scalars(
            select(TimelineEventModel)
            .where(TimelineEventModel.case_id == id)
            .order_by(TimelineEventModel.created_at.asc())
        )
    )
    events_data = [
        {
            "date": e.event_date,
            "title": e.title,
            "description": e.description,
            "is_important": e.is_important,
            "page": 1,
        }
        for e in events
    ]

    agent = VoiceBriefAgent(voice_gateway=get_voice_gateway())
    spoken_script, source_refs = agent.build_spoken_script(
        case_title=case.title,
        case_number=case.case_number,
        court=case.court,
        summary_text=summary_text,
        events=events_data,
        depth=payload.depth,
    )

    # Synthesize audio
    audio_bytes = agent.voice_gateway.synthesize(
        text=spoken_script,
        voice_id=payload.voice_id or settings.VOICEFLOW_VOICE_ID,
        language=payload.language,
    )
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None

    # Handle ephemeral vs persisted audio
    audio_path = None
    if settings.VOICE_STORE_AUDIO:
        audio_dir = os.path.join(settings.ENCRYPTED_STORAGE_DIR, "audio", id)
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"brief_{payload.depth}_{payload.language}.wav")
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

    # Calculate duration estimate
    word_count = len(spoken_script.split())
    duration_sec = max(10, int((word_count / 130) * 60))

    # Persist brief metadata
    brief_model = VoiceBriefModel(
        case_id=case.id,
        depth=payload.depth,
        language=payload.language,
        spoken_script=spoken_script,
        audio_path=audio_path,
        duration_estimate_sec=duration_sec,
        source_refs=json.dumps([s.model_dump() for s in source_refs]),
        confidence=1.0,
        needs_human_review=False,
        disclaimer="This is an artificial intelligence decision-support brief for advocates, not formal legal advice.",
    )
    db.add(brief_model)
    db.commit()

    return VoiceBriefOutput(
        case_id=case.id,
        depth=payload.depth,
        language=payload.language,
        spoken_script=spoken_script,
        audio_base64=audio_b64,
        duration_estimate_sec=duration_sec,
        source_refs=source_refs,
        confidence=1.0,
        needs_human_review=False,
        disclaimer="This is an artificial intelligence decision-support brief for advocates, not formal legal advice.",
    )


@router.post("/{id}/voice/ask", response_model=VoiceQuestionOutput)
def ask_voice_question(
    id: str,
    payload: VoiceQuestionInput,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Grounded spoken question answering with strict refusal of ungrounded questions."""
    case = db.scalar(select(CaseModel).where(CaseModel.id == id))
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{id}' not found.")
    _verify_case_access(case, current_user)

    agent = VoiceQAAgent(voice_gateway=get_voice_gateway())
    return agent.run(payload)


@router.get("/{id}/voice/briefs", response_model=List[VoiceBriefOutput])
def list_voice_briefs(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """List previously synthesized voice briefs for a case."""
    case = db.scalar(select(CaseModel).where(CaseModel.id == id))
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{id}' not found.")
    _verify_case_access(case, current_user)

    records = list(
        db.scalars(
            select(VoiceBriefModel)
            .where(VoiceBriefModel.case_id == id)
            .order_by(VoiceBriefModel.created_at.desc())
        )
    )

    outputs = []
    for r in records:
        refs_data = json.loads(r.source_refs) if r.source_refs else []
        refs = [SourceRef.model_validate(x) for x in refs_data]
        outputs.append(
            VoiceBriefOutput(
                case_id=r.case_id,
                depth=r.depth,
                language=r.language,
                spoken_script=r.spoken_script,
                audio_base64=None,
                duration_estimate_sec=r.duration_estimate_sec,
                source_refs=refs,
                confidence=r.confidence or 1.0,
                needs_human_review=r.needs_human_review or False,
                disclaimer=r.disclaimer,
            )
        )
    return outputs
