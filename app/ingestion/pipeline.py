"""Document ingestion pipeline supporting PDF, text, and multilingual Devanagari legal records.

Follows Hard Rule 2: Every extracted fact carries source reference with page and character offsets.
Follows Hard Rule 5: Writes append-only audit log.
Follows Hard Rule 6: Stores documents encrypted at rest with AES-256-GCM.
Follows Hard Rule 7: Handles Devanagari and mixed Hindi/English/Hinglish properly.
"""

import io
import hashlib
import uuid
from typing import List, Optional, Tuple
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.security.encryption import encrypt_bytes
from app.security.audit import record_audit_event
from app.ingestion.devanagari import normalize_devanagari_text, detect_language_mix
from app.ingestion.chunker import OffsetPreservingChunker, TextChunk
from app.llm.embedding import get_embedding_client
from app.db.models import DocumentModel, DocumentChunkModel


class IngestedDocumentResult(BaseModel):
    document_id: str
    filename: str
    sha256_hash: str
    page_count: int
    detected_language: str
    chunks_count: int
    chunks: List[TextChunk]


class DocumentIngestor:
    """Manages secure document ingestion, encryption, multilingual text extraction, and chunking."""

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunker = OffsetPreservingChunker(
            target_chunk_size=chunk_size,
            overlap_size=chunk_overlap,
        )

    def extract_pages(self, raw_bytes: bytes, filename: str) -> List[Tuple[int, str]]:
        """Extracts text per page, returning a list of (page_number_1_indexed, text)."""
        filename_lower = filename.lower()
        pages: List[Tuple[int, str]] = []

        if filename_lower.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(raw_bytes))
            for idx, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                normalized = normalize_devanagari_text(extracted)
                pages.append((idx + 1, normalized))
        else:
            # Plain text or Markdown document
            try:
                decoded = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                decoded = raw_bytes.decode("latin-1", errors="replace")
            normalized = normalize_devanagari_text(decoded)
            pages.append((1, normalized))

        return pages

    def ingest(
        self,
        raw_bytes: bytes,
        filename: str,
        db_session: Optional[Session] = None,
        actor: str = "advocate_user",
    ) -> IngestedDocumentResult:
        """Process document: encrypt at rest, extract text, chunk with offsets, embed, and store."""
        doc_id = str(uuid.uuid4())
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Hard Rule 6: Encrypt raw content at rest using AES-256-GCM
        encrypted_blob = encrypt_bytes(raw_bytes)

        # Extract text per page
        pages = self.extract_pages(raw_bytes, filename)
        page_count = len(pages)

        # Detect overall document language
        combined_sample = " ".join([p[1] for p in pages[:3]])
        detected_lang = detect_language_mix(combined_sample)

        # Chunk pages while strictly preserving character offsets
        all_chunks: List[TextChunk] = []
        global_chunk_idx = 0
        for page_num, page_text in pages:
            page_chunks = self.chunker.chunk_page(
                page_text=page_text,
                page_number=page_num,
                start_chunk_idx=global_chunk_idx,
            )
            all_chunks.extend(page_chunks)
            global_chunk_idx += len(page_chunks)

        # Generate embeddings for chunks
        embed_client = get_embedding_client()
        chunk_texts = [c.text for c in all_chunks]
        embeddings = embed_client.embed_documents(chunk_texts) if chunk_texts else []

        # Store to database if session provided
        if db_session:
            doc_model = DocumentModel(
                id=doc_id,
                filename=filename,
                mime_type="application/pdf" if filename.lower().endswith(".pdf") else "text/plain",
                encrypted_content=encrypted_blob,
                sha256_hash=sha256_hash,
                detected_language=detected_lang,
                page_count=page_count,
            )
            db_session.add(doc_model)
            db_session.flush()

            for chunk, emb in zip(all_chunks, embeddings):
                chunk_model = DocumentChunkModel(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    text=chunk.text,
                    embedding=emb,
                )
                db_session.add(chunk_model)
            
            db_session.commit()

        # Hard Rule 5: Append-only audit record
        record_audit_event(
            event_type="DOCUMENT_INGEST",
            actor=actor,
            resource_id=doc_id,
            input_payload={"filename": filename, "sha256": sha256_hash, "size_bytes": len(raw_bytes)},
            output_payload={
                "page_count": page_count,
                "detected_language": detected_lang,
                "chunks_count": len(all_chunks),
            },
            status="SUCCESS",
        )

        return IngestedDocumentResult(
            document_id=doc_id,
            filename=filename,
            sha256_hash=sha256_hash,
            page_count=page_count,
            detected_language=detected_lang,
            chunks_count=len(all_chunks),
            chunks=all_chunks,
        )

