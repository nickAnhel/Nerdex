"""add content views and sessions

Revision ID: 1a2b3c4d5e6f
Revises: 8d0a1b2c3d4e
Create Date: 2026-05-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "8d0a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("views_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "content_view_sessions",
        sa.Column("view_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anonymous_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_position_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_position_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("watched_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_counted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counted_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("last_position_seconds >= 0", name="ck_content_view_sessions_last_position_non_negative"),
        sa.CheckConstraint("max_position_seconds >= 0", name="ck_content_view_sessions_max_position_non_negative"),
        sa.CheckConstraint("watched_seconds >= 0", name="ck_content_view_sessions_watched_seconds_non_negative"),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_content_view_sessions_progress_percent_range"),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("view_session_id"),
    )
    op.create_index(
        "ix_content_view_sessions_viewer_last_seen",
        "content_view_sessions",
        ["viewer_id", sa.text("last_seen_at DESC")],
    )
    op.create_index(
        "ix_content_view_sessions_content_viewer_started",
        "content_view_sessions",
        ["content_id", "viewer_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "uq_content_view_sessions_counted_viewer_day",
        "content_view_sessions",
        ["content_id", "viewer_id", "counted_date"],
        unique=True,
        postgresql_where=sa.text("is_counted = true AND viewer_id IS NOT NULL AND counted_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_content_view_sessions_counted_viewer_day", table_name="content_view_sessions")
    op.drop_index("ix_content_view_sessions_content_viewer_started", table_name="content_view_sessions")
    op.drop_index("ix_content_view_sessions_viewer_last_seen", table_name="content_view_sessions")
    op.drop_table("content_view_sessions")
    op.drop_column("content", "views_count")
