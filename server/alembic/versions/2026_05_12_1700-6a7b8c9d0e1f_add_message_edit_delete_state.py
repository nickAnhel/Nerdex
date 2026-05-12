"""add message edit delete state

Revision ID: 6a7b8c9d0e1f
Revises: 5e6f7a8b9c0d
Create Date: 2026-05-12 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, None] = "5e6f7a8b9c0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_deleted_by_users",
        "messages",
        "users",
        ["deleted_by"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_messages_deleted_at",
        "messages",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_deleted_at", table_name="messages")
    op.drop_constraint(
        "fk_messages_deleted_by_users",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "deleted_by")
    op.drop_column("messages", "deleted_at")
    op.drop_column("messages", "edited_at")
