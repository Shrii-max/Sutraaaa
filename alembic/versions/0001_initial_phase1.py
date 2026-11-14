"""Phase 1 initial migration: legal intelligence models, pgvector, HNSW, GIN, and audit triggers.

Revision ID: 0001_initial_phase1
Revises: 
Create Date: 2026-11-14 12:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector
from app.config import get_settings

revision: str = "0001_initial_phase1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = get_settings().EMBED_DIM


def upgrade() -> None:
    # 1. Enable pgvector extension if on PostgreSQL
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="advocate"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 3. Cases table
    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("case_number", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("court", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"])
    op.create_index("ix_cases_user_id", "cases", ["user_id"])

    # 4. Documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("doc_type", sa.String(length=50), server_default="other"),
        sa.Column("detected_language", sa.String(length=50), server_default="mixed"),
        sa.Column("page_count", sa.Integer(), server_default="1"),
        sa.Column("mime_type", sa.String(length=100), server_default="application/pdf"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_sha256_hash", "documents", ["sha256_hash"])
    op.create_index("ix_documents_case_id", "documents", ["case_id"])

    # 5. Document Pages
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("language", sa.String(length=50), server_default="en"),
        sa.Column("script", sa.String(length=50), server_default="Latin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])

    # 6. Document Chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM) if is_postgres else sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # 7. Facts table
    op.create_table(
        "facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("item_data", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_facts_document_id", "facts", ["document_id"])
    op.create_index("ix_facts_case_id", "facts", ["case_id"])

    # 8. Validation Issues table
    op.create_table(
        "validation_issues",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("severity", sa.String(length=30), server_default="MEDIUM"),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_refs", sa.Text(), server_default="[]"),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_validation_issues_document_id", "validation_issues", ["document_id"])

    # 9. Timeline Events table
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_date", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_important", sa.Boolean(), server_default="false"),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_timeline_events_case_id", "timeline_events", ["case_id"])

    # 10. Contradictions table
    op.create_table(
        "contradictions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("statement_a", sa.Text(), nullable=False),
        sa.Column("statement_b", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_a", sa.Text(), nullable=False),
        sa.Column("source_b", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=30), server_default="MEDIUM"),
        sa.Column("confidence", sa.Float(), server_default="0.85"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contradictions_case_id", "contradictions", ["case_id"])

    # 11. Summaries table
    op.create_table(
        "summaries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("key_issues", sa.Text(), server_default="[]"),
        sa.Column("relief_sought", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.90"),
        sa.Column("needs_human_review", sa.Boolean(), server_default="false"),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_summaries_case_id", "summaries", ["case_id"])

    # 12. Judgments table
    op.create_table(
        "judgments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("court", sa.String(length=150), nullable=False),
        sa.Column("date", sa.String(length=50), nullable=False),
        sa.Column("citation", sa.String(length=150), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_judgments_title", "judgments", ["title"])
    op.create_index("ix_judgments_court", "judgments", ["court"])
    op.create_index("ix_judgments_citation", "judgments", ["citation"], unique=True)

    # 13. Judgment Chunks with GIN index on tsvector and HNSW index on vector
    op.create_table(
        "judgment_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("judgment_id", sa.String(length=36), sa.ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM) if is_postgres else sa.Text(), nullable=True),
        sa.Column("tsv", postgresql.TSVECTOR() if is_postgres else sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_judgment_chunks_judgment_id", "judgment_chunks", ["judgment_id"])

    if is_postgres:
        # GIN index for full-text search
        op.create_index(
            "ix_judgment_chunks_tsv_gin",
            "judgment_chunks",
            ["tsv"],
            postgresql_using="gin",
        )
        # HNSW index for vector cosine similarity
        op.create_index(
            "ix_judgment_chunks_embedding_hnsw",
            "judgment_chunks",
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )

    # 14. Audit Logs table (Append-Only)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("input_payload", sa.Text(), nullable=True),
        sa.Column("output_payload", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("needs_human_review", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="SUCCESS"),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])

    # 15. Install append-only trigger on audit_logs
    if is_postgres:
        op.execute("""
            CREATE OR REPLACE FUNCTION audit_logs_block_modifications()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs table is append-only: UPDATE and DELETE operations are prohibited';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION audit_logs_block_modifications();
        """)
    else:
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs table is append-only: UPDATE blocked');
            END;
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs table is append-only: DELETE blocked');
            END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS audit_logs_block_modifications();")
    else:
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update;")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete;")

    op.drop_table("audit_logs")
    op.drop_table("judgment_chunks")
    op.drop_table("judgments")
    op.drop_table("summaries")
    op.drop_table("contradictions")
    op.drop_table("timeline_events")
    op.drop_table("validation_issues")
    op.drop_table("facts")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("cases")
    op.drop_table("users")

