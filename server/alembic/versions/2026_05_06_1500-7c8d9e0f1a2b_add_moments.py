"""add moments

Revision ID: 7c8d9e0f1a2b
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c8d9e0f1a2b"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE content_type_enum ADD VALUE IF NOT EXISTS 'moment'")
    op.create_table(
        "moment_details",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("caption", sa.String(length=2200), server_default="", nullable=False),
        sa.Column("publish_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(caption) <= 2200", name="ck_moment_details_caption_length"),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )


def downgrade() -> None:
    op.drop_table("moment_details")
