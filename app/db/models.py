"""SQLAlchemy 2.0 ORM models for LexAgent Foundation (Phase 1).

Includes User, Case, Document, DocumentPage, Fact, ValidationIssueModel,
TimelineEventModel, ContradictionModel, SummaryModel, Judgment, JudgmentChunk,
and append-only AuditLog.
"""

import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    LargeBinary,
    TypeDecorator,
    Index,
    event,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.config import get_settings
from app.db.session import Base

settings = get_settings()
EMBED_DIM = settings.EMBED_DIM


class AdaptiveVector(TypeDecorator):
    """Custom SQLAlchemy type that uses pgvector.Vector on PostgreSQL and JSON/Text on SQLite."""
    impl = Text
    cache_ok = True

    def __init__(self, dim: int = EMBED_DIM):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value) if hasattr(value, "__iter__") else value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return []
        return value


class AdaptiveTSVector(TypeDecorator):
    """Uses TSVECTOR on PostgreSQL and Text on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(Text())


class UserModel(Base):
    """User accounts for legal advocates, researchers, and administrators."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="advocate")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    cases = relationship("CaseModel", back_populates="user", cascade="all, delete-orphan")


class CaseModel(Base):
    """Legal matter or case file managing multiple documents and proceedings."""
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    case_number = Column(String(100), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    court = Column(String(150), nullable=True)
    status = Column(String(50), default="open")
    # DPDP Compliance fields
    dpdp_purpose = Column(Text, default="Legal Defense & Case Preparation")
    retention_until = Column(DateTime(timezone=True), nullable=True)
    is_crypto_shredded = Column(Boolean, default=False)
    shredded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", back_populates="cases")
    documents = relationship("DocumentModel", back_populates="case", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEventModel", back_populates="case", cascade="all, delete-orphan")
    contradictions = relationship("ContradictionModel", back_populates="case", cascade="all, delete-orphan")
    summaries = relationship("SummaryModel", back_populates="case", cascade="all, delete-orphan")


class DocumentModel(Base):
    """Legal document stored encrypted at rest (AES-256-GCM) with provenance."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=True)  # encrypted blob path on filesystem vault
    encrypted_content = Column(LargeBinary, nullable=True)  # in-db encrypted blob option
    sha256_hash = Column(String(64), nullable=False, index=True)
    doc_type = Column(String(50), default="other")  # FIR, petition, judgment, affidavit, etc.
    detected_language = Column(String(50), default="mixed")
    page_count = Column(Integer, default=1)
    mime_type = Column(String(100), default="application/pdf")
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, running, done, failed, needs_review
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("CaseModel", back_populates="documents")
    pages = relationship("DocumentPageModel", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunkModel", back_populates="document", cascade="all, delete-orphan")
    facts = relationship("FactModel", back_populates="document", cascade="all, delete-orphan")
    validation_issues = relationship("ValidationIssueModel", back_populates="document", cascade="all, delete-orphan")
    processing_steps = relationship("ProcessingStepModel", back_populates="document", cascade="all, delete-orphan")


class DocumentPageModel(Base):
    """Individual page extraction with OCR confidence and language/script detection."""
    __tablename__ = "document_pages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    language = Column(String(50), default="en")
    script = Column(String(50), default="Latin")
    # OCR v2 & Visual Evidence Markers
    raw_image_enc_path = Column(Text, nullable=True)
    has_handwriting = Column(Boolean, default=False)
    has_stamp = Column(Boolean, default=False)
    has_signature = Column(Boolean, default=False)
    word_confidences_json = Column(Text, nullable=True)
    is_corrected = Column(Boolean, default=False)
    corrected_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentModel", back_populates="pages")


# Alias for backward compatibility
DocumentPage = DocumentPageModel


class DocumentChunkModel(Base):
    """Semantic chunk preserving character start/end offsets for SourceRef."""
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(AdaptiveVector(EMBED_DIM), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentModel", back_populates="chunks")


class FactModel(Base):
    """Extracted facts with mandatory provenance and confidence."""
    __tablename__ = "facts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    category = Column(String(80), nullable=False)  # party, date, section, amount, location, statement
    item_data = Column(Text, nullable=False)  # JSON serialized data
    source_ref = Column(Text, nullable=False)  # JSON serialized SourceRef
    confidence = Column(Float, default=1.0)
    # Fact Verification & NLI Entailment
    entailment_status = Column(String(32), default="supports")  # supports, contradicts, insufficient
    verifier_confidence = Column(Float, default=1.0)
    verifier_reason = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String(36), nullable=True)
    review_action = Column(String(50), nullable=True)  # approved, corrected, rejected
    correction_data = Column(Text, nullable=True)  # JSON serialized correction
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentModel", back_populates="facts")


class ProcessingStepModel(Base):
    """Execution step record for pipeline crash recovery, retries, and step-level state."""
    __tablename__ = "processing_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    step_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, running, done, failed, needs_review
    engine = Column(String(50), default="rules", nullable=True)  # regex, rules, llm, nli, embedder, tesseract, pymupdf, tts
    fallback_taken = Column(Boolean, default=False, nullable=False)
    attempt = Column(Integer, default=0)
    state_payload = Column(Text, nullable=True)  # JSON serialized step output for resume
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentModel", back_populates="processing_steps")


class ValidationIssueModel(Base):
    """Procedural, limitation, or evidentiary validation defect."""
    __tablename__ = "validation_issues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    severity = Column(String(30), default="MEDIUM")  # HIGH, MEDIUM, LOW, CRITICAL
    category = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    source_refs = Column(Text, default="[]")  # JSON serialized list of SourceRef
    suggestion = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentModel", back_populates="validation_issues")


class TimelineEventModel(Base):
    """Chronological event tied to a case file."""
    __tablename__ = "timeline_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    event_date = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    is_important = Column(Boolean, default=False)
    source_ref = Column(Text, nullable=False)  # JSON serialized SourceRef
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("CaseModel", back_populates="timeline_events")


class ContradictionModel(Base):
    """Detected contradiction between statements or depositions."""
    __tablename__ = "contradictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    statement_a = Column(Text, nullable=False)
    statement_b = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    source_a = Column(Text, nullable=False)  # JSON serialized SourceRef
    source_b = Column(Text, nullable=False)  # JSON serialized SourceRef
    severity = Column(String(30), default="MEDIUM")
    confidence = Column(Float, default=0.85)
    # 3-Vote LLM Jury & Feedback
    jury_votes_contradict = Column(Integer, default=0)
    jury_votes_consistent = Column(Integer, default=0)
    jury_votes_unclear = Column(Integer, default=0)
    lawyer_verdict = Column(String(32), nullable=True)  # ACCEPTED, REJECTED, IGNORED
    lawyer_feedback_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("CaseModel", back_populates="contradictions")


class SummaryModel(Base):
    """Executive case summary and legal framing."""
    __tablename__ = "summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    summary_text = Column(Text, nullable=False)
    key_issues = Column(Text, default="[]")  # JSON list
    relief_sought = Column(Text, nullable=True)
    confidence = Column(Float, default=0.90)
    needs_human_review = Column(Boolean, default=False)
    disclaimer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("CaseModel", back_populates="summaries")


class Judgment(Base):
    """Indian court judgments (Supreme Court / High Courts / Tribunals)."""
    __tablename__ = "judgments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    court = Column(String(150), nullable=False, index=True)
    date = Column(String(50), nullable=False)
    citation = Column(String(150), unique=True, nullable=False, index=True)
    bench = Column(String(255), nullable=True)
    source_url = Column(String(512), nullable=True)
    retrieved_on = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    verification_status = Column(String(50), default="unverified", nullable=False)
    sections_cited = Column(Text, default="[]")  # JSON serialized list of statutory sections
    outcome = Column(String(100), nullable=True)  # e.g. Allowed, Dismissed, Quashed, Remanded, Conviction Upheld
    summary = Column(Text, nullable=True)
    ratio_decidendi = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    # Provenance, Licensing & Overruled Law Metadata
    license_note = Column(Text, nullable=True)
    is_overruled = Column(Boolean, default=False, index=True)
    overruled_by_citation = Column(String(150), nullable=True)
    embedding = Column(AdaptiveVector(EMBED_DIM), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    chunks = relationship("JudgmentChunk", back_populates="judgment", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "case_title" in kwargs and "title" not in kwargs:
            kwargs["title"] = kwargs.pop("case_title")
        if "judgment_date" in kwargs and "date" not in kwargs:
            kwargs["date"] = kwargs.pop("judgment_date")
        full_text = kwargs.get("full_text")
        if full_text is not None and (not str(full_text).strip() or len(str(full_text).strip()) < 100):
            raise ValueError("Judgment rejected: full_text cannot be empty or shorter than 100 characters.")
        super().__init__(**kwargs)

    @property
    def case_title(self) -> str:
        return self.title

    @case_title.setter
    def case_title(self, val: str):
        self.title = val

    @property
    def judgment_date(self) -> str:
        return self.date

    @judgment_date.setter
    def judgment_date(self, val: str):
        self.date = val


# Alias PrecedentCaseModel for backward compatibility
PrecedentCaseModel = Judgment


class CaseJudgmentMatch(Base):
    """Saved relationship between a workspace case and a public judgment."""
    __tablename__ = "case_judgment_matches"

    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    judgment_id = Column(String(36), ForeignKey("judgments.id", ondelete="CASCADE"), primary_key=True)
    score = Column(Float, nullable=False)
    matched_terms = Column(Text, nullable=False)


class JudgmentChunk(Base):
    """Chunks of judgments with pgvector embedding, tsvector column, GIN index, and HNSW index."""
    __tablename__ = "judgment_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    judgment_id = Column(String(36), ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(AdaptiveVector(EMBED_DIM), nullable=True)
    tsv = Column(AdaptiveTSVector, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    judgment = relationship("Judgment", back_populates="chunks")

    __table_args__ = (
        # GIN index for full-text search on tsvector
        Index("ix_judgment_chunks_tsv_gin", "tsv", postgresql_using="gin"),
        # HNSW index for high-speed approximate nearest neighbor vector search
        Index(
            "ix_judgment_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class StatuteSection(Base):
    """Bare-act statutory sections with embeddings and full-text search."""
    __tablename__ = "statute_sections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    act = Column(String(100), nullable=False, index=True)  # e.g. IPC, CrPC, BNS, BNSS, NI Act
    section_no = Column(String(50), nullable=False, index=True)  # e.g. 420, 138, 161
    heading = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    source_url = Column(String(512), nullable=True)
    retrieved_on = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    verification_status = Column(String(50), default="unverified", nullable=False)
    embedding = Column(AdaptiveVector(EMBED_DIM), nullable=True)
    tsv = Column(AdaptiveTSVector, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_statute_sections_tsv_gin", "tsv", postgresql_using="gin"),
        Index(
            "ix_statute_sections_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class AuditLogModel(Base):
    """Append-only audit log table. Blocked from UPDATE or DELETE via database trigger."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    event_type = Column(String(80), nullable=False, index=True)
    actor = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    input_payload = Column(Text, nullable=True)
    output_payload = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    needs_human_review = Column(Boolean, nullable=True)
    status = Column(String(30), default="SUCCESS")
    prev_hash = Column(String(64), nullable=False)
    record_hash = Column(String(64), nullable=False)


# Append-only enforcement listeners (prevent UPDATE/DELETE in Python runtime and trigger in DB)
@event.listens_for(AuditLogModel, "before_update")
def block_audit_log_update(mapper, connection, target):
    raise PermissionError("audit_logs table is append-only: UPDATE operations are strictly prohibited.")


@event.listens_for(AuditLogModel, "before_delete")
def block_audit_log_delete(mapper, connection, target):
    raise PermissionError("audit_logs table is append-only: DELETE operations are strictly prohibited.")


class IngestionQuarantineModel(Base):
    """Quarantine store for malformed judgments, statutes, or invalid legal records."""
    __tablename__ = "ingestion_quarantined_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_file = Column(String(255), nullable=False)
    record_type = Column(String(50), nullable=False)  # judgment, statute
    raw_payload = Column(Text, nullable=False)
    validation_errors = Column(Text, nullable=False)  # JSON list of validation error strings
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentTranslationModel(Base):
    """Cache and persistent store for multilingual document and summary translations."""
    __tablename__ = "document_translations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    source_language = Column(String(20), default="en", nullable=False)
    target_language = Column(String(20), nullable=False, index=True)
    translation_type = Column(String(50), default="document", nullable=False)  # document, summary
    translated_text = Column(Text, nullable=False)
    alignments_json = Column(Text, nullable=True)  # JSON serialized list of SentenceAlignment
    issues_json = Column(Text, default="[]", nullable=False)
    confidence = Column(Float, default=0.90)
    needs_human_review = Column(Boolean, default=False)
    disclaimer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VoiceBriefModel(Base):
    """Spoken audio briefs generated for advocates."""
    __tablename__ = "voice_briefs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    depth = Column(String(20), default="2min", nullable=False)
    language = Column(String(20), default="en", nullable=False)
    spoken_script = Column(Text, nullable=False)
    audio_path = Column(String(255), nullable=True)  # stored only when VOICE_STORE_AUDIO=true
    duration_estimate_sec = Column(Integer, default=120)
    source_refs = Column(Text, default="[]", nullable=False)  # JSON list of SourceRef
    confidence = Column(Float, default=1.0)
    needs_human_review = Column(Boolean, default=False)
    disclaimer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



