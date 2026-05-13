"""add chat read state

Revision ID: 9a0b1c2d3e4f
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a0b1c2d3e4f"
down_revision: Union[str, None] = "4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_user",
        sa.Column("last_read_message_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "chat_user",
        sa.Column(
            "is_muted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_foreign_key(
        "fk_chat_user_last_read_message_id_messages",
        "chat_user",
        "messages",
        ["last_read_message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_chat_user_last_read_message_id",
        "chat_user",
        ["last_read_message_id"],
    )
    op.create_index(
        "ix_messages_chat_created_at",
        "messages",
        ["chat_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_chat_created_at", table_name="messages")
    op.drop_index("ix_chat_user_last_read_message_id", table_name="chat_user")
    op.drop_constraint(
        "fk_chat_user_last_read_message_id_messages",
        "chat_user",
        type_="foreignkey",
    )
    op.drop_column("chat_user", "is_muted")
    op.drop_column("chat_user", "last_read_message_id")
