"""add user activity events

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-13 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


activity_action_type_enum = postgresql.ENUM(
    "content_view",
    "content_like",
    "content_dislike",
    "content_reaction_removed",
    "content_comment",
    "user_follow",
    "user_unfollow",
    name="activity_action_type_enum",
    create_type=False,
)
content_type_enum = postgresql.ENUM(
    "post",
    "article",
    "video",
    "moment",
    name="content_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    activity_action_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "user_activity_events",
        sa.Column("activity_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", activity_action_type_enum, nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", content_type_enum, nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.comment_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_event_id"),
    )
    op.create_index(
        "ix_user_activity_events_user_created_at",
        "user_activity_events",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_activity_events_user_action_created_at",
        "user_activity_events",
        ["user_id", "action_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_activity_events_user_content_type_created_at",
        "user_activity_events",
        ["user_id", "content_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_activity_events_content_created_at",
        "user_activity_events",
        ["content_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_activity_events_target_user_created_at",
        "user_activity_events",
        ["target_user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_user_activity_events_target_user_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_content_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_content_type_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_action_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_created_at", table_name="user_activity_events")
    op.drop_table("user_activity_events")
    bind = op.get_bind()
    activity_action_type_enum.drop(bind, checkfirst=True)
