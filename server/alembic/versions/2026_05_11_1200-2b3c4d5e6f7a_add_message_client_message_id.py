"""add message client message id

Revision ID: 2b3c4d5e6f7a
Revises: 7c8d9e0f1a2b
Create Date: 2026-05-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b3c4d5e6f7a"
down_revision: Union[str, None] = "7c8d9e0f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("client_message_id", sa.Uuid(), nullable=True))
    op.alter_column(
        "messages",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.create_unique_constraint(
        "uq_messages_chat_user_client_message_id",
        "messages",
        ["chat_id", "user_id", "client_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_chat_user_client_message_id",
        "messages",
        type_="unique",
    )
    op.alter_column(
        "messages",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.drop_column("messages", "client_message_id")
