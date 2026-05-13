"""add message shared content

Revision ID: 3f4a5b6c7d8e
Revises: 8b9c0d1e2f3a
Create Date: 2026-05-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f4a5b6c7d8e"
down_revision: Union[str, None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_shared_content",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content.content_id"],
            name="fk_message_shared_content_content_id_content",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.message_id"],
            name="fk_message_shared_content_message_id_messages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_message_shared_content"),
    )
    op.create_index(
        "ix_message_shared_content_content_id",
        "message_shared_content",
        ["content_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_message_shared_content_content_id",
        table_name="message_shared_content",
    )
    op.drop_table("message_shared_content")
