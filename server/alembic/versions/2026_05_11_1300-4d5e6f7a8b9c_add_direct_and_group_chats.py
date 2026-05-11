"""add direct and group chats

Revision ID: 4d5e6f7a8b9c
Revises: 2b3c4d5e6f7a
Create Date: 2026-05-11 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, None] = "2b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "chat_type",
            sa.String(),
            nullable=True,
            server_default="group",
        ),
    )
    op.add_column("chats", sa.Column("direct_key", sa.String(), nullable=True))
    op.add_column(
        "chat_user",
        sa.Column(
            "role",
            sa.String(),
            nullable=True,
            server_default="member",
        ),
    )

    op.execute("UPDATE chats SET chat_type = 'group' WHERE chat_type IS NULL")
    op.execute("UPDATE chat_user SET role = 'member' WHERE role IS NULL")
    op.execute(
        """
        UPDATE chat_user
        SET role = 'owner'
        FROM chats
        WHERE chat_user.chat_id = chats.chat_id
          AND chat_user.user_id = chats.owner_id
        """
    )

    op.alter_column("chats", "chat_type", nullable=False)
    op.alter_column("chat_user", "role", nullable=False)
    op.create_check_constraint(
        "ck_chats_chat_type",
        "chats",
        "chat_type in ('direct', 'group')",
    )
    op.create_check_constraint(
        "ck_chat_user_role",
        "chat_user",
        "role in ('owner', 'member')",
    )
    op.create_index("ix_chat_user_user_id", "chat_user", ["user_id"])
    op.create_index(
        "uq_chats_direct_key",
        "chats",
        ["direct_key"],
        unique=True,
        postgresql_where=sa.text("direct_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_chats_direct_key", table_name="chats")
    op.drop_index("ix_chat_user_user_id", table_name="chat_user")
    op.drop_constraint("ck_chat_user_role", "chat_user", type_="check")
    op.drop_constraint("ck_chats_chat_type", "chats", type_="check")
    op.drop_column("chat_user", "role")
    op.drop_column("chats", "direct_key")
    op.drop_column("chats", "chat_type")
