"""Phase A v2 reliability migration: OCR v2 fields, Fact verification, Contradiction jury, and Quarantine table.

Revision ID: 0002_phase_a_v2_reliability
Revises: 0001_initial_phase1
Create Date: 2026-11-14 17:50:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase_a_v2_reliability"
down_revision: Union[str, None] = "0001_initial_phase1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add DPDP fields to cases
    op.add_column("cases", sa.Column("dpdp_purpose", sa.Text(), nullable=True, server_default="Legal Defense & Case Preparation"))
    op.add_column("cases", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("is_crypto_shredded", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("cases", sa.Column("shredded_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Add OCR v2 fields to document_pages
    op.add_column("document_pages", sa.Column("raw_image_enc_path", sa.Text(), nullable=True))
    op.add_column("document_pages", sa.Column("has_handwriting", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("document_pages", sa.Column("has_stamp", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("document_pages", sa.Column("has_signature", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("document_pages", sa.Column("word_confidences_json", sa.Text(), nullable=True))
    op.add_column("document_pages", sa.Column("is_corrected", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("document_pages", sa.Column("corrected_text", sa.Text(), nullable=True))

    # 3. Add Fact verification fields to facts
    op.add_column("facts", sa.Column("entailment_status", sa.String(length=32), nullable=True, server_default="supports"))
    op.add_column("facts", sa.Column("verifier_confidence", sa.Float(), nullable=True, server_default="1.0"))
    op.add_column("facts", sa.Column("verifier_reason", sa.Text(), nullable=True))
    op.add_column("facts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))

    # 4. Add Contradiction jury fields to contradictions
    op.add_column("contradictions", sa.Column("jury_votes_contradict", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("contradictions", sa.Column("jury_votes_consistent", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("contradictions", sa.Column("jury_votes_unclear", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("contradictions", sa.Column("lawyer_verdict", sa.String(length=32), nullable=True))
    op.add_column("contradictions", sa.Column("lawyer_feedback_notes", sa.Text(), nullable=True))

    # 5. Add Provenance & Overruled metadata to judgments
    op.add_column("judgments", sa.Column("license_note", sa.Text(), nullable=True))
    op.add_column("judgments", sa.Column("is_overruled", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("judgments", sa.Column("overruled_by_citation", sa.String(length=150), nullable=True))
    op.create_index("ix_judgments_is_overruled", "judgments", ["is_overruled"])

    # 6. Create ingestion quarantine table
    op.create_table(
        "ingestion_quarantined_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("validation_errors", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingestion_quarantined_records")
    op.drop_index("ix_judgments_is_overruled", "judgments")
    op.drop_column("judgments", "overruled_by_citation")
    op.drop_column("judgments", "is_overruled")
    op.drop_column("judgments", "license_note")
    op.drop_column("contradictions", "lawyer_feedback_notes")
    op.drop_column("contradictions", "lawyer_verdict")
    op.drop_column("contradictions", "jury_votes_unclear")
    op.drop_column("contradictions", "jury_votes_consistent")
    op.drop_column("contradictions", "jury_votes_contradict")
    op.drop_column("facts", "verified_at")
    op.drop_column("facts", "verifier_reason")
    op.drop_column("facts", "verifier_confidence")
    op.drop_column("facts", "entailment_status")
    op.drop_column("document_pages", "corrected_text")
    op.drop_column("document_pages", "is_corrected")
    op.drop_column("document_pages", "word_confidences_json")
    op.drop_column("document_pages", "has_signature")
    op.drop_column("document_pages", "has_stamp")
    op.drop_column("document_pages", "has_handwriting")
    op.drop_column("document_pages", "raw_image_enc_path")
    op.drop_column("cases", "shredded_at")
    op.drop_column("cases", "is_crypto_shredded")
    op.drop_column("cases", "retention_until")
    op.drop_column("cases", "dpdp_purpose")

