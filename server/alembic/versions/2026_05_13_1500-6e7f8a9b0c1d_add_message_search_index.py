"""add message search index

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-05-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6e7f8a9b0c1d"
down_revision: Union[str, None] = "5d6e7f8a9b0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_content_search",
        "messages",
        [sa.text("to_tsvector('simple', coalesce(content, ''))")],
        postgresql_using="gin",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_messages_content_search", table_name="messages")
