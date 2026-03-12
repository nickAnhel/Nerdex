"""Add comments tables

Revision ID: d2c3b4a5f6e7
Revises: b7a1c2d3e4f5
Create Date: 2026-03-11 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d2c3b4a5f6e7"
down_revision: Union[str, None] = "b7a1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reaction_type_enum = postgresql.ENUM(
    "like",
    "dislike",
    name="reaction_type_enum",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    reaction_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "comments",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_comment_id", sa.Uuid(), nullable=True),
        sa.Column("root_comment_id", sa.Uuid(), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("body_text", sa.String(length=2048), nullable=False),
        sa.Column("replies_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dislikes_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("depth >= 0", name="ck_comments_depth_non_negative"),
        sa.CheckConstraint("char_length(body_text) <= 2048", name="ck_comments_body_text_max_length"),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_comment_id"], ["comments.comment_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["root_comment_id"], ["comments.comment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id"),
    )
    op.create_index(
        "ix_comments_content_parent_created_at_desc",
        "comments",
        ["content_id", "parent_comment_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_comments_root_parent_created_at_asc",
        "comments",
        ["root_comment_id", "parent_comment_id", sa.text("created_at ASC")],
        unique=False,
    )
    op.create_index("ix_comments_author_id", "comments", ["author_id"], unique=False)

    op.create_table(
        "comment_reactions",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reaction_type", reaction_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.comment_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "user_id"),
    )
    op.create_index("ix_comment_reactions_user_id", "comment_reactions", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index("ix_comment_reactions_user_id", table_name="comment_reactions")
    op.drop_table("comment_reactions")

    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_root_parent_created_at_asc", table_name="comments")
    op.drop_index("ix_comments_content_parent_created_at_desc", table_name="comments")
    op.drop_table("comments")
