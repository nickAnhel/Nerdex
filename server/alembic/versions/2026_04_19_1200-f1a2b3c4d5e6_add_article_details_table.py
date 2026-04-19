"""add article details table

Revision ID: f1a2b3c4d5e6
Revises: c6d7e8f9a0b1
Create Date: 2026-04-19 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_details",
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reading_time_minutes", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "toc",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("seo_title", sa.String(length=300), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
        sa.CheckConstraint("char_length(slug) BETWEEN 1 AND 180", name="ck_article_details_slug_length"),
        sa.CheckConstraint("char_length(seo_title) <= 300", name="ck_article_details_seo_title_length"),
        sa.CheckConstraint(
            "seo_description IS NULL OR char_length(seo_description) <= 320",
            name="ck_article_details_seo_description_length",
        ),
        sa.CheckConstraint("word_count >= 0", name="ck_article_details_word_count_non_negative"),
        sa.CheckConstraint(
            "reading_time_minutes >= 1",
            name="ck_article_details_reading_time_minutes_positive",
        ),
    )
    op.create_index("ix_article_details_slug", "article_details", ["slug"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_article_details_slug", table_name="article_details")
    op.drop_table("article_details")
