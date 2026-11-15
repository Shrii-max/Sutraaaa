"""Phase C Voice Delivery migration: voice_briefs table.

Revision ID: 0004_phase_c_voice
Revises: 0003_phase_b_multilingual
Create Date: 2026-11-14 19:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_phase_c_voice"
down_revision: Union[str, None] = "0003_phase_b_multilingual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_briefs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depth", sa.String(length=20), nullable=False, server_default="2min"),
        sa.Column("language", sa.String(length=20), nullable=False, server_default="en"),
        sa.Column("spoken_script", sa.Text(), nullable=False),
        sa.Column("audio_path", sa.String(length=255), nullable=True),
        sa.Column("duration_estimate_sec", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("source_refs", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("needs_human_review", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_voice_briefs_case_id", "voice_briefs", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_voice_briefs_case_id", table_name="voice_briefs")
    op.drop_table("voice_briefs")
