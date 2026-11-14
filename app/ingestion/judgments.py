"""Judgment ingestion pipeline with paragraph chunking, batch embeddings, and idempotent upsert.

Follows Requirement:
1. /app/ingestion: an ingestion pipeline for judgments and legal knowledge.
   JSONL fields: id, title, court, date, citation, source_url, bench, sections_cited[], outcome, full_text.
   Chunk by paragraph (300-500 tokens with overlap), store chunk to judgment mapping,
   generate embeddings in batches via Embedder, upsert idempotently.
"""

import json
import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Judgment, JudgmentChunk
from app.llm.client import Embedder, LocalEmbeddingClient

logger = logging.getLogger(__name__)


class JudgmentIngestItem(BaseModel):
    """Input contract for judgment ingestion."""
    id: Optional[str] = None
    title: str = Field(..., min_length=2, description="Case title, e.g. State of Maharashtra v. Suresh")
    court: str = Field(..., min_length=2, description="Judicial forum, e.g. Supreme Court of India")
    date: str = Field(..., min_length=2, description="Judgment date")
    citation: str = Field(..., min_length=2, description="Official law report citation, e.g. AIR 2021 SC 105")
    source_url: Optional[str] = None
    bench: Optional[str] = None
    sections_cited: List[str] = Field(default_factory=list, description="Statutory sections cited in judgment")
    outcome: Optional[str] = Field(default=None, description="Disposal outcome: Allowed, Dismissed, Quashed, etc.")
    full_text: str = Field(..., min_length=10, description="Full verbatim text or substantive excerpt of judgment")


def approximate_token_count(text: str) -> int:
    """Fast token count approximation (~0.75 words per token for legal text)."""
    words = len(text.split())
    return max(1, int(words * 1.33))


def chunk_judgment_text(
    full_text: str,
    target_tokens: int = 400,
    min_tokens: int = 250,
    max_tokens: int = 500,
    overlap_tokens: int = 60,
) -> List[str]:
    """Chunk judgment text by paragraph (300-500 tokens with semantic overlap)."""
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]
    if not raw_paras:
        raw_paras = [p.strip() for p in full_text.splitlines() if p.strip()]

    if not raw_paras:
        return [full_text.strip()] if full_text.strip() else []

    chunks: List[str] = []
    current_chunk_paras: List[str] = []
    current_tokens = 0

    for para in raw_paras:
        p_tokens = approximate_token_count(para)

        # If single paragraph exceeds max_tokens, split it by sentence
        if p_tokens > max_tokens:
            if current_chunk_paras:
                chunks.append("\n\n".join(current_chunk_paras))
                current_chunk_paras = []
                current_tokens = 0

            sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", para) if s.strip()]
            sub_chunk = []
            sub_toks = 0
            for s in sentences:
                st = approximate_token_count(s)
                if sub_toks + st > target_tokens and sub_chunk:
                    chunks.append(" ".join(sub_chunk))
                    # Overlap with last sentence
                    overlap = [sub_chunk[-1]] if len(sub_chunk) > 1 else []
                    sub_chunk = overlap + [s]
                    sub_toks = sum(approximate_token_count(x) for x in sub_chunk)
                else:
                    sub_chunk.append(s)
                    sub_toks += st
            if sub_chunk:
                chunks.append(" ".join(sub_chunk))
            continue

        if current_tokens + p_tokens > max_tokens and current_tokens >= min_tokens:
            chunk_body = "\n\n".join(current_chunk_paras)
            chunks.append(chunk_body)

            # Build overlap from the tail paragraph
            overlap_para = current_chunk_paras[-1] if current_chunk_paras else ""
            if approximate_token_count(overlap_para) <= overlap_tokens:
                current_chunk_paras = [overlap_para, para]
                current_tokens = approximate_token_count(overlap_para) + p_tokens
            else:
                current_chunk_paras = [para]
                current_tokens = p_tokens
        else:
            current_chunk_paras.append(para)
            current_tokens += p_tokens

    if current_chunk_paras:
        chunks.append("\n\n".join(current_chunk_paras))

    return chunks if chunks else [full_text]


def ingest_judgment_items(
    items: List[JudgmentIngestItem],
    session: Session,
    embedder: Optional[Embedder] = None,
    batch_size: int = 16,
) -> Tuple[int, int]:
    """Ingest a list of judgment items idempotently with batch embeddings.

    Returns:
        Tuple[int, int]: (judgments_upserted_count, chunks_stored_count)
    """
    embed_client = embedder or LocalEmbeddingClient()
    total_judgments = 0
    total_chunks = 0

    for item in items:
        # Check if judgment already exists by citation
        existing = session.query(Judgment).filter(Judgment.citation == item.citation.strip()).first()
        j_id = existing.id if existing else (item.id or str(uuid.uuid4()))

        # Generate chunk texts
        chunks = chunk_judgment_text(item.full_text)
        if not chunks:
            chunks = [item.full_text[:1000]]

        # Compute embeddings in batches
        all_embeddings: List[List[float]] = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vecs = embed_client.embed(batch)
            all_embeddings.extend(vecs)

        # Judgment-level summary embedding
        summary_repr = (
            f"{item.title}. Court: {item.court}. Date: {item.date}. "
            f"Sections: {', '.join(item.sections_cited)}. Outcome: {item.outcome or 'Adjudicated'}. "
            f"{chunks[0][:500]}"
        )
        j_embedding = embed_client.embed([summary_repr])[0]

        if existing:
            # Update metadata
            existing.title = item.title
            existing.court = item.court
            existing.date = item.date
            existing.bench = item.bench
            existing.source_url = item.source_url
            existing.sections_cited = json.dumps(item.sections_cited)
            existing.outcome = item.outcome
            existing.full_text = item.full_text
            existing.embedding = j_embedding

            # Idempotent replacement of chunks
            session.query(JudgmentChunk).filter(JudgmentChunk.judgment_id == existing.id).delete()
            session.flush()
        else:
            new_j = Judgment(
                id=j_id,
                title=item.title,
                court=item.court,
                date=item.date,
                citation=item.citation.strip(),
                bench=item.bench,
                source_url=item.source_url,
                sections_cited=json.dumps(item.sections_cited),
                outcome=item.outcome,
                full_text=item.full_text,
                embedding=j_embedding,
            )
            session.add(new_j)
            session.flush()

        # Insert new chunks
        for idx, (chunk_text, vec) in enumerate(zip(chunks, all_embeddings)):
            chunk_row = JudgmentChunk(
                id=str(uuid.uuid4()),
                judgment_id=j_id,
                chunk_index=idx,
                text=chunk_text,
                embedding=vec,
            )
            session.add(chunk_row)
            total_chunks += 1

        total_judgments += 1

    session.commit()
    return total_judgments, total_chunks


def load_judgments_from_jsonl(file_path: Union[str, Path]) -> List[JudgmentIngestItem]:
    """Parse JSONL file into validated JudgmentIngestItem models."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found at: {file_path}")

    items: List[JudgmentIngestItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            try:
                data = json.loads(line_str)
                items.append(JudgmentIngestItem(**data))
            except Exception as e:
                logger.warning(f"Error parsing line {line_no} in {file_path}: {e}")
                continue

    return items

