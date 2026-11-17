"""Deterministic assessment rules for the Moot Court hearing graph."""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Judgment


class PointAssessment(BaseModel):
    strength: float = Field(ge=0, le=1)
    precedent: float = Field(ge=0, le=1)
    statute: float = Field(ge=0, le=1)
    factual_consistency: float = Field(ge=0, le=1)
    responsiveness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    contradiction: float = Field(default=0, ge=0, le=1)
    unanswered: float = Field(default=0, ge=0, le=1)


def update_leaning(
    prior: float,
    point: PointAssessment,
    side: Literal["petitioner", "respondent"],
    *,
    repeated: bool = False,
) -> float:
    """Return the new issue score on the petitioner's 0–100 axis."""
    if repeated:
        return prior
    merit = (
        0.35 * point.strength
        + 0.25 * point.precedent
        + 0.20 * point.statute
        + 0.15 * point.factual_consistency
        + 0.05 * point.responsiveness
    )
    delta = 10 * merit * point.confidence - 4 * point.contradiction - 2 * point.unanswered
    direction = 1 if side == "petitioner" else -1
    return min(100.0, max(0.0, prior + direction * delta))


def verify_authorities(db: Session, authority_ids: list[str]) -> list[Judgment]:
    """Hydrate cited IDs from the corpus and drop missing or disqualified records."""
    if not authority_ids:
        return []
    rows = db.scalars(
        select(Judgment).where(
            Judgment.id.in_(authority_ids),
            Judgment.verification_status == "verified",
            Judgment.is_overruled.is_(False),
        )
    )
    by_id = {row.id: row for row in rows if row.citation.strip() and row.source_url}
    return [by_id[key] for key in dict.fromkeys(authority_ids) if key in by_id]

