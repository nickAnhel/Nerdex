"""extend reaction type enum

Revision ID: 5d6e7f8a9b0c
Revises: 4c5d6e7f8a9b
Create Date: 2026-05-13 14:15:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "5d6e7f8a9b0c"
down_revision: Union[str, None] = "4c5d6e7f8a9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REACTION_VALUES = (
    "heart",
    "fire",
    "joy",
    "cry",
    "thinking",
    "exploding_head",
    "clap",
    "pray",
)


def upgrade() -> None:
    for reaction_value in REACTION_VALUES:
        op.execute(f"ALTER TYPE reaction_type_enum ADD VALUE IF NOT EXISTS '{reaction_value}'")


def downgrade() -> None:
    pass
