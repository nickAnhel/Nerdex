"""Refactor posts into content

Revision ID: 9f3b4c2d1a0e
Revises: 2e6c89f8995c
Create Date: 2026-03-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9f3b4c2d1a0e"
down_revision: Union[str, None] = "2e6c89f8995c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


content_type_enum = postgresql.ENUM(
    "post",
    "article",
    "video",
    "course",
    name="content_type_enum",
    create_type=False,
)
content_status_enum = postgresql.ENUM(
    "draft",
    "published",
    "archived",
    "deleted",
    name="content_status_enum",
    create_type=False,
)
content_visibility_enum = postgresql.ENUM(
    "public",
    "followers",
    "private",
    name="content_visibility_enum",
    create_type=False,
)
reaction_type_enum = postgresql.ENUM(
    "like",
    "dislike",
    name="reaction_type_enum",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    content_type_enum.create(bind, checkfirst=True)
    content_status_enum.create(bind, checkfirst=True)
    content_visibility_enum.create(bind, checkfirst=True)
    reaction_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "content",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", content_type_enum, nullable=False),
        sa.Column("status", content_status_enum, nullable=False),
        sa.Column("visibility", content_visibility_enum, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dislikes_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["author_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )
    op.create_index("ix_content_author_id", "content", ["author_id"], unique=False)
    op.create_index(
        "ix_content_status_visibility_published_at",
        "content",
        ["status", "visibility", sa.text("published_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_content_type_status_published_at",
        "content",
        ["content_type", "status", sa.text("published_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_content_author_status_visibility_created_at",
        "content",
        ["author_id", "status", "visibility", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "post_details",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )

    op.create_table(
        "content_reactions",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reaction_type", reaction_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "user_id"),
    )
    op.create_index("ix_content_reactions_user_id", "content_reactions", ["user_id"], unique=False)

    op.execute(
        """
        INSERT INTO content (
            content_id,
            author_id,
            content_type,
            status,
            visibility,
            title,
            excerpt,
            created_at,
            updated_at,
            published_at,
            deleted_at,
            comments_count,
            likes_count,
            dislikes_count,
            metadata
        )
        SELECT
            posts.post_id,
            posts.user_id,
            'post'::content_type_enum,
            'published'::content_status_enum,
            'public'::content_visibility_enum,
            NULL,
            NULL,
            posts.created_at,
            posts.created_at,
            posts.created_at,
            NULL,
            0,
            0,
            0,
            '{}'::jsonb
        FROM posts
        """
    )
    op.execute(
        """
        INSERT INTO post_details (content_id, body_text)
        SELECT posts.post_id, posts.content
        FROM posts
        """
    )
    op.execute(
        """
        WITH merged_reactions AS (
            SELECT
                post_id AS content_id,
                user_id,
                'like'::reaction_type_enum AS reaction_type,
                created_at
            FROM user_post_likes
            UNION ALL
            SELECT
                post_id AS content_id,
                user_id,
                'dislike'::reaction_type_enum AS reaction_type,
                created_at
            FROM user_post_dislikes
        ),
        deduplicated_reactions AS (
            SELECT DISTINCT ON (content_id, user_id)
                content_id,
                user_id,
                reaction_type,
                created_at
            FROM merged_reactions
            ORDER BY content_id, user_id, created_at DESC, reaction_type DESC
        )
        INSERT INTO content_reactions (content_id, user_id, reaction_type, created_at)
        SELECT
            content_id,
            user_id,
            reaction_type,
            created_at
        FROM deduplicated_reactions
        """
    )
    op.execute(
        """
        WITH reaction_counts AS (
            SELECT
                content_id,
                COUNT(*) FILTER (WHERE reaction_type = 'like') AS likes_count,
                COUNT(*) FILTER (WHERE reaction_type = 'dislike') AS dislikes_count
            FROM content_reactions
            GROUP BY content_id
        )
        UPDATE content
        SET
            likes_count = COALESCE(reaction_counts.likes_count, 0),
            dislikes_count = COALESCE(reaction_counts.dislikes_count, 0)
        FROM reaction_counts
        WHERE content.content_id = reaction_counts.content_id
        """
    )

    op.drop_table("user_post_likes")
    op.drop_table("user_post_dislikes")
    op.drop_table("posts")


def downgrade() -> None:
    """Downgrade schema."""

    op.create_table(
        "posts",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dislikes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.create_table(
        "user_post_dislikes",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.post_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )
    op.create_table(
        "user_post_likes",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.post_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )

    op.execute(
        """
        INSERT INTO posts (post_id, content, created_at, user_id, likes, dislikes)
        SELECT
            content.content_id,
            post_details.body_text,
            COALESCE(content.published_at, content.created_at),
            content.author_id,
            content.likes_count,
            content.dislikes_count
        FROM content
        JOIN post_details ON post_details.content_id = content.content_id
        WHERE content.content_type = 'post'
        """
    )
    op.execute(
        """
        INSERT INTO user_post_likes (post_id, user_id, created_at)
        SELECT content_id, user_id, created_at
        FROM content_reactions
        WHERE reaction_type = 'like'
        """
    )
    op.execute(
        """
        INSERT INTO user_post_dislikes (post_id, user_id, created_at)
        SELECT content_id, user_id, created_at
        FROM content_reactions
        WHERE reaction_type = 'dislike'
        """
    )

    op.drop_index("ix_content_reactions_user_id", table_name="content_reactions")
    op.drop_table("content_reactions")
    op.drop_table("post_details")
    op.drop_index("ix_content_author_status_visibility_created_at", table_name="content")
    op.drop_index("ix_content_type_status_published_at", table_name="content")
    op.drop_index("ix_content_status_visibility_published_at", table_name="content")
    op.drop_index("ix_content_author_id", table_name="content")
    op.drop_table("content")

    bind = op.get_bind()
    reaction_type_enum.drop(bind, checkfirst=True)
    content_visibility_enum.drop(bind, checkfirst=True)
    content_status_enum.drop(bind, checkfirst=True)
    content_type_enum.drop(bind, checkfirst=True)
