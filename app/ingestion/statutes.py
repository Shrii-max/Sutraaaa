"""Statutory bare-act section ingestion pipeline with idempotent upsert.

Follows Requirement:
1. Ingestion of bare-act sections (act, section_no, heading, text).
   Generate embeddings in batches via Embedder, upsert idempotently.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Union
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import StatuteSection
from app.llm.client import Embedder, LocalEmbeddingClient

logger = logging.getLogger(__name__)


class StatuteIngestItem(BaseModel):
    """Input contract for bare-act statutory section ingestion."""
    id: Optional[str] = None
    act: str = Field(..., min_length=2, description="Short statute code, e.g. IPC, CrPC, BNS, BNSS, NI Act")
    section_no: str = Field(..., min_length=1, description="Section number, e.g. 420, 138, 161")
    heading: str = Field(..., min_length=2, description="Section heading or marginal note")
    text: str = Field(..., min_length=5, description="Full statutory text of the provision")


def ingest_statute_items(
    items: List[StatuteIngestItem],
    session: Session,
    embedder: Optional[Embedder] = None,
    batch_size: int = 16,
) -> int:
    """Ingest bare-act statutory provisions idempotently with vector embeddings.

    Returns:
        int: Total sections upserted.
    """
    embed_client = embedder or LocalEmbeddingClient()
    total_upserted = 0

    for item in items:
        clean_act = item.act.strip().upper()
        clean_sec = item.section_no.strip()

        # Check existing by (act, section_no)
        existing = (
            session.query(StatuteSection)
            .filter(StatuteSection.act == clean_act)
            .filter(StatuteSection.section_no == clean_sec)
            .first()
        )

        repr_text = f"{clean_act} Section {clean_sec}: {item.heading}. {item.text}"
        vec = embed_client.embed([repr_text])[0]

        if existing:
            existing.heading = item.heading
            existing.text = item.text
            existing.embedding = vec
        else:
            row = StatuteSection(
                id=item.id or str(uuid.uuid4()),
                act=clean_act,
                section_no=clean_sec,
                heading=item.heading,
                text=item.text,
                embedding=vec,
            )
            session.add(row)

        total_upserted += 1

    session.commit()
    return total_upserted


def load_statutes_from_jsonl(file_path: Union[str, Path]) -> List[StatuteIngestItem]:
    """Parse JSONL file into validated StatuteIngestItem models."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Statutes JSONL file not found at: {file_path}")

    items: List[StatuteIngestItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            try:
                data = json.loads(line_str)
                items.append(StatuteIngestItem(**data))
            except Exception as e:
                logger.warning(f"Error parsing statute line {line_no} in {file_path}: {e}")
                continue

    return items

