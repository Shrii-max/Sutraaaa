"""Phase B multilingual migration: document_translations table.

Revision ID: 0003_phase_b_multilingual
Revises: 0002_phase_a_v2_reliability
Create Date: 2026-11-14 19:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_phase_b_multilingual"
down_revision: Union[str, None] = "0002_phase_a_v2_reliability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_translations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_language", sa.String(length=20), nullable=False, server_default="en"),
        sa.Column("target_language", sa.String(length=20), nullable=False),
        sa.Column("translation_type", sa.String(length=50), nullable=False, server_default="document"),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("alignments_json", sa.Text(), nullable=True),
        sa.Column("issues_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="0.90"),
        sa.Column("needs_human_review", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_translations_document_id", "document_translations", ["document_id"])
    op.create_index("ix_document_translations_case_id", "document_translations", ["case_id"])
    op.create_index("ix_document_translations_content_hash", "document_translations", ["content_hash"])
    op.create_index("ix_document_translations_target_language", "document_translations", ["target_language"])


def downgrade() -> None:
    op.drop_index("ix_document_translations_target_language", table_name="document_translations")
    op.drop_index("ix_document_translations_content_hash", table_name="document_translations")
    op.drop_index("ix_document_translations_case_id", table_name="document_translations")
    op.drop_index("ix_document_translations_document_id", table_name="document_translations")
    op.drop_table("document_translations")

