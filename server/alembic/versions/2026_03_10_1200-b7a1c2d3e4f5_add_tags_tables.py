"""Add tags tables

Revision ID: b7a1c2d3e4f5
Revises: 3c4d5e6f7a8b
Create Date: 2026-03-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7a1c2d3e4f5"
down_revision: Union[str, None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "tags",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("tag_id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "content_tags",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "tag_id"),
    )

    op.create_index("ix_content_tags_tag_id", "content_tags", ["tag_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index("ix_content_tags_tag_id", table_name="content_tags")
    op.drop_table("content_tags")
    op.drop_table("tags")
