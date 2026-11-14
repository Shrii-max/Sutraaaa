"""Hybrid Vector and Keyword Retriever supporting English, Hindi, and Hinglish.

Combines semantic dense embeddings with BM25 keyword matching for legal terminology.
"""

import re
import numpy as np
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, select

from app.llm.embedding import get_embedding_client
from app.db.models import PrecedentCaseModel, DocumentChunkModel


class RetrievedChunkResult(BaseModel):
    id: str
    text: str
    metadata: dict
    score: float


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.array(v1, dtype=float)
    b = np.array(v2, dtype=float)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class HybridRetriever:
    """Retrieves document chunks and case law precedents with hybrid vector + lexical ranking."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.embed_client = get_embedding_client()

    def search_precedents(
        self,
        query: str,
        top_k: int = 3,
        court_filter: Optional[str] = None,
    ) -> List[PrecedentCaseModel]:
        """Search local precedent cases using dense vector similarity and keyword matching.
        
        Guaranteed to pull ONLY from the local database.
        """
        query_vec = self.embed_client.embed_query(query)
        is_postgres = "postgresql" in str(self.session.bind.url)

        candidates: List[PrecedentCaseModel] = []

        if is_postgres:
            try:
                # Use pgvector cosine distance operator <=>
                vec_str = f"[{','.join(str(x) for x in query_vec)}]"
                court_clause = "AND court ILIKE :court" if court_filter else ""
                sql = text(
                    f"""
                    SELECT id, case_title, citation, court, judgment_date, bench, summary, ratio_decidendi, full_text,
                           1 - (embedding <=> :vec::vector) AS sim
                    FROM precedent_cases
                    WHERE 1=1 {court_clause}
                    ORDER BY embedding <=> :vec::vector
                    LIMIT :limit
                    """
                )
                params = {"vec": vec_str, "limit": top_k}
                if court_filter:
                    params["court"] = f"%{court_filter}%"

                result = self.session.execute(sql, params).fetchall()
                for row in result:
                    case = self.session.get(PrecedentCaseModel, row[0])
                    if case:
                        candidates.append(case)
                if candidates:
                    return candidates
            except Exception:
                # If pgvector query fails, fall back to Python-based similarity
                self.session.rollback()

        # In-memory Python cosine similarity fallback (for SQLite, testing, or dialect independence)
        query_stmt = select(PrecedentCaseModel)
        if court_filter:
            query_stmt = query_stmt.where(PrecedentCaseModel.court.ilike(f"%{court_filter}%"))
        
        all_cases = self.session.execute(query_stmt).scalars().all()
        if not all_cases:
            return []

        scored = []
        tokens = set(re.findall(r"\w+", query.lower()))

        for case in all_cases:
            score = 0.0
            if case.embedding:
                case_emb = case.embedding
                if isinstance(case_emb, str):
                    import json
                    case_emb = json.loads(case_emb)
                score = cosine_similarity(query_vec, case_emb)

            # Keyword lexical boost
            case_text = f"{case.case_title} {case.summary} {case.ratio_decidendi}".lower()
            overlap = sum(1 for t in tokens if t in case_text)
            lexical_boost = min(0.3, overlap * 0.05)
            total_score = (score * 0.7) + lexical_boost

            scored.append((total_score, case))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [case for _, case in scored[:top_k]]

    def search_document_chunks(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[DocumentChunkModel]:
        """Search chunks within a specific ingested document."""
        query_vec = self.embed_client.embed_query(query)
        chunks = (
            self.session.execute(
                select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
            )
            .scalars()
            .all()
        )
        if not chunks:
            return []

        scored = []
        for ch in chunks:
            sim = 0.0
            if ch.embedding:
                emb = ch.embedding
                if isinstance(emb, str):
                    import json
                    emb = json.loads(emb)
                sim = cosine_similarity(query_vec, emb)
            scored.append((sim, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ch for _, ch in scored[:top_k]]

