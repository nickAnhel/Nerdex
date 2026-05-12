"""add message replies

Revision ID: 8b9c0d1e2f3a
Revises: 6a7b8c9d0e1f
Create Date: 2026-05-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b9c0d1e2f3a"
down_revision: Union[str, None] = "6a7b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("reply_to_message_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_reply_to_message_id_messages",
        "messages",
        "messages",
        ["reply_to_message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_messages_chat_reply_to_message_id",
        "messages",
        ["chat_id", "reply_to_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_chat_reply_to_message_id", table_name="messages")
    op.drop_constraint(
        "fk_messages_reply_to_message_id_messages",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "reply_to_message_id")
