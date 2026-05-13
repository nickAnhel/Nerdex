"""add message reactions

Revision ID: 4c5d6e7f8a9b
Revises: 3f4a5b6c7d8e
Create Date: 2026-05-13 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4c5d6e7f8a9b"
down_revision: Union[str, None] = "3f4a5b6c7d8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reaction_type_enum = postgresql.ENUM(
    "like",
    "dislike",
    name="reaction_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    reaction_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "message_reactions",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reaction_type", reaction_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["message_id"], ["messages.message_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", "user_id"),
    )
    op.create_index("ix_message_reactions_user_id", "message_reactions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_reactions_user_id", table_name="message_reactions")
    op.drop_table("message_reactions")
