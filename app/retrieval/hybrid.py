"""Hybrid Dense (pgvector) and Sparse (Full-Text) Retriever with RRF and Reranker Interface.

Follows Requirement:
2. /app/retrieval/hybrid.py: HybridRetriever:
   - dense search on pgvector (cosine) + sparse search on Postgres full-text (with SQLite fallback)
   - metadata filters (court, year range, sections_cited, outcome)
   - Reciprocal Rank Fusion (RRF), then optional Reranker interface (bge-reranker-v2-m3, default no-op)
   - returns chunks with judgment_id and scores
"""

import json
import logging
import math
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, select

from app.config import get_settings
from app.db.models import Judgment, JudgmentChunk, StatuteSection
from app.llm.client import Embedder, LocalEmbeddingClient

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    """A retrieved passage with judgment mapping and ranking scores."""
    chunk_id: str
    judgment_id: str
    chunk_index: int = 0
    text: str
    score: float
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    rrf_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalFilter(BaseModel):
    """Metadata filters for targeted legal research."""
    court: Optional[str] = None
    year_range: Optional[Tuple[int, int]] = None  # (min_year, max_year)
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    sections_cited: Optional[List[str]] = None
    outcome: Optional[str] = None


class Reranker(ABC):
    """Abstract interface for passage re-ranking."""

    @abstractmethod
    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Re-rank candidate chunks according to query relevance."""
        pass


class NoOpReranker(Reranker):
    """Default no-op reranker preserving RRF hybrid ordering."""

    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        return chunks


class BGEReranker(Reranker):
    """bge-reranker-v2-m3 interface for high-precision cross-encoder re-ranking."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._available = False
        try:
            from sentence_transformers import CrossEncoder
            self._encoder = CrossEncoder(model_name)
            self._available = True
        except Exception:
            self._encoder = None

    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        if not self._available or not chunks:
            return chunks
        try:
            pairs = [[query, c.text] for c in chunks]
            scores = self._encoder.predict(pairs)
            for chunk, score in zip(chunks, scores):
                chunk.score = float(score)
            chunks.sort(key=lambda x: x.score, reverse=True)
            return chunks
        except Exception:
            return chunks


def _cosine_sim(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class HybridRetriever:
    """Hybrid Retriever combining dense pgvector search and sparse full-text search with RRF."""

    def __init__(
        self,
        db_session: Session,
        embedder: Optional[Embedder] = None,
        reranker: Optional[Reranker] = None,
        rrf_k: int = 60,
    ):
        self.session = db_session
        self.embedder = embedder or LocalEmbeddingClient()
        self.reranker = reranker or NoOpReranker()
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[RetrievalFilter] = None,
    ) -> List[RetrievedChunk]:
        """Perform hybrid retrieval with dense vector + sparse keyword search and RRF fusion."""
        if not query or not query.strip():
            return []

        # 1. Dense search
        dense_results = self._dense_search(query, top_k * 3, filters)

        # 2. Sparse full-text / keyword search
        sparse_results = self._sparse_search(query, top_k * 3, filters)

        # 3. Reciprocal Rank Fusion (RRF)
        fused = self._reciprocal_rank_fusion(dense_results, sparse_results)

        # 4. Apply optional Reranker
        reranked = self.reranker.rerank(query, fused)

        # 5. Apply Retrieval Score Floor (drops low-relevance noise)
        settings = get_settings()
        floor = settings.RETRIEVAL_SCORE_FLOOR
        if floor and floor > 0.0:
            filtered = [
                c for c in reranked
                if (c.sparse_score or 0.0) > 0.0 or (c.dense_score or 0.0) >= floor
            ]
            return filtered[:top_k]

        return reranked[:top_k]

    def _dense_search(
        self, query: str, limit: int, filters: Optional[RetrievalFilter]
    ) -> List[RetrievedChunk]:
        """Dense embedding search on pgvector (with fallback for SQLite)."""
        query_vec = self.embedder.embed_query(query)
        is_postgres = "postgresql" in str(self.session.bind.url).lower() if self.session.bind else False

        if is_postgres:
            try:
                vec_str = f"[{','.join(str(x) for x in query_vec)}]"
                sql = text("""
                    SELECT c.id, c.judgment_id, c.chunk_index, c.text,
                           1 - (c.embedding <=> :vec::vector) AS sim,
                           j.title, j.court, j.date, j.citation, j.sections_cited, j.outcome
                    FROM judgment_chunks c
                    JOIN judgments j ON c.judgment_id = j.id
                    WHERE 1=1
                    ORDER BY c.embedding <=> :vec::vector
                    LIMIT :limit
                """)
                res = self.session.execute(sql, {"vec": vec_str, "limit": limit}).fetchall()
                chunks = []
                for row in res:
                    m = {
                        "title": row[5],
                        "court": row[6],
                        "date": row[7],
                        "citation": row[8],
                        "sections_cited": row[9],
                        "outcome": row[10],
                    }
                    if self._matches_filter(m, filters):
                        chunks.append(RetrievedChunk(
                            chunk_id=row[0],
                            judgment_id=row[1],
                            chunk_index=row[2],
                            text=row[3],
                            score=float(row[4]),
                            dense_score=float(row[4]),
                            metadata=m,
                        ))
                return chunks
            except Exception as e:
                logger.warning(f"pgvector query failed, falling back to Python vector search: {e}")
                self.session.rollback()

        # Fallback Python-based vector search (SQLite or generic SQL)
        stmt = select(JudgmentChunk, Judgment).join(Judgment, JudgmentChunk.judgment_id == Judgment.id)
        records = self.session.execute(stmt).all()

        scored: List[Tuple[float, JudgmentChunk, Judgment]] = []
        for c_row, j_row in records:
            meta = {
                "title": j_row.title,
                "court": j_row.court,
                "date": j_row.date,
                "citation": j_row.citation,
                "sections_cited": j_row.sections_cited,
                "outcome": j_row.outcome,
                "is_overruled": getattr(j_row, "is_overruled", False),
                "overruled_by_citation": getattr(j_row, "overruled_by_citation", None),
            }
            if not self._matches_filter(meta, filters):
                continue

            emb = c_row.embedding
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = []
            sim = _cosine_sim(query_vec, emb) if emb else 0.0
            scored.append((sim, c_row, j_row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, c_row, j_row in scored[:limit]:
            results.append(RetrievedChunk(
                chunk_id=c_row.id,
                judgment_id=c_row.judgment_id,
                chunk_index=c_row.chunk_index,
                text=c_row.text,
                score=round(sim, 4),
                dense_score=round(sim, 4),
                metadata={
                    "title": j_row.title,
                    "court": j_row.court,
                    "date": j_row.date,
                    "citation": j_row.citation,
                    "sections_cited": j_row.sections_cited,
                    "outcome": j_row.outcome,
                },
            ))
        return results

    def _sparse_search(
        self, query: str, limit: int, filters: Optional[RetrievalFilter]
    ) -> List[RetrievedChunk]:
        """Sparse search using Postgres full-text search (with BM25 keyword fallback)."""
        is_postgres = "postgresql" in str(self.session.bind.url).lower() if self.session.bind else False

        if is_postgres:
            try:
                sql = text("""
                    SELECT c.id, c.judgment_id, c.chunk_index, c.text,
                           ts_rank(c.tsv, plainto_tsquery('english', :query)) AS rank,
                           j.title, j.court, j.date, j.citation, j.sections_cited, j.outcome
                    FROM judgment_chunks c
                    JOIN judgments j ON c.judgment_id = j.id
                    WHERE c.tsv @@ plainto_tsquery('english', :query)
                    ORDER BY rank DESC
                    LIMIT :limit
                """)
                res = self.session.execute(sql, {"query": query, "limit": limit}).fetchall()
                chunks = []
                for row in res:
                    m = {
                        "title": row[5],
                        "court": row[6],
                        "date": row[7],
                        "citation": row[8],
                        "sections_cited": row[9],
                        "outcome": row[10],
                    }
                    if self._matches_filter(m, filters):
                        chunks.append(RetrievedChunk(
                            chunk_id=row[0],
                            judgment_id=row[1],
                            chunk_index=row[2],
                            text=row[3],
                            score=float(row[4]),
                            sparse_score=float(row[4]),
                            metadata=m,
                        ))
                return chunks
            except Exception as e:
                logger.warning(f"Postgres full-text query failed, falling back to lexical search: {e}")
                self.session.rollback()

        # Lexical keyword / BM25 term overlap fallback (for SQLite)
        stmt = select(JudgmentChunk, Judgment).join(Judgment, JudgmentChunk.judgment_id == Judgment.id)
        records = self.session.execute(stmt).all()

        q_terms = set(re.findall(r"\w{3,}", query.lower()))
        scored = []
        for c_row, j_row in records:
            meta = {
                "title": j_row.title,
                "court": j_row.court,
                "date": j_row.date,
                "citation": j_row.citation,
                "sections_cited": j_row.sections_cited,
                "outcome": j_row.outcome,
                "is_overruled": getattr(j_row, "is_overruled", False),
                "overruled_by_citation": getattr(j_row, "overruled_by_citation", None),
            }
            if not self._matches_filter(meta, filters):
                continue

            text_lower = c_row.text.lower()
            overlap_count = sum(1 for term in q_terms if term in text_lower)
            if overlap_count > 0:
                score = overlap_count / len(q_terms)
                scored.append((score, c_row, j_row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, c_row, j_row in scored[:limit]:
            results.append(RetrievedChunk(
                chunk_id=c_row.id,
                judgment_id=c_row.judgment_id,
                chunk_index=c_row.chunk_index,
                text=c_row.text,
                score=round(score, 4),
                sparse_score=round(score, 4),
                metadata={
                    "title": j_row.title,
                    "court": j_row.court,
                    "date": j_row.date,
                    "citation": j_row.citation,
                    "sections_cited": j_row.sections_cited,
                    "outcome": j_row.outcome,
                },
            ))
        return results

    def _reciprocal_rank_fusion(
        self, dense: List[RetrievedChunk], sparse: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Combine dense and sparse rankings using Reciprocal Rank Fusion (RRF)."""
        chunk_map: Dict[str, RetrievedChunk] = {}
        rrf_scores: Dict[str, float] = {}

        for rank, item in enumerate(dense, start=1):
            chunk_map[item.chunk_id] = item
            rrf_scores[item.chunk_id] = rrf_scores.get(item.chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        for rank, item in enumerate(sparse, start=1):
            if item.chunk_id not in chunk_map:
                chunk_map[item.chunk_id] = item
            else:
                chunk_map[item.chunk_id].sparse_score = item.sparse_score
            rrf_scores[item.chunk_id] = rrf_scores.get(item.chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        combined: List[RetrievedChunk] = []
        for c_id, rrf_val in rrf_scores.items():
            chunk = chunk_map[c_id]
            chunk.rrf_score = round(rrf_val, 6)
            chunk.score = chunk.rrf_score
            combined.append(chunk)

        combined.sort(key=lambda x: x.score, reverse=True)
        return combined

    @staticmethod
    def _matches_filter(meta: Dict[str, Any], filters: Optional[RetrievalFilter]) -> bool:
        if not filters:
            return True

        # Court filter
        if filters.court:
            if filters.court.lower() not in (meta.get("court") or "").lower():
                return False

        # Year range filter
        date_str = meta.get("date") or ""
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
        year_val = int(year_match.group(1)) if year_match else None

        min_y = filters.min_year or (filters.year_range[0] if filters.year_range else None)
        max_y = filters.max_year or (filters.year_range[1] if filters.year_range else None)

        if min_y is not None and year_val is not None and year_val < min_y:
            return False
        if max_y is not None and year_val is not None and year_val > max_y:
            return False

        # Sections cited filter
        if filters.sections_cited:
            raw_secs = meta.get("sections_cited") or "[]"
            sec_list = []
            if isinstance(raw_secs, list):
                sec_list = raw_secs
            elif isinstance(raw_secs, str):
                try:
                    sec_list = json.loads(raw_secs)
                except Exception:
                    sec_list = [raw_secs]
            combined_secs = " ".join(sec_list).lower()
            if not any(s.lower() in combined_secs for s in filters.sections_cited):
                return False

        # Outcome filter
        if filters.outcome:
            out = (meta.get("outcome") or "").lower()
            if filters.outcome.lower() not in out:
                return False

        return True

