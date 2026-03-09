"""Reduce post max length to 2048

Revision ID: 3c4d5e6f7a8b
Revises: 9f3b4c2d1a0e
Create Date: 2026-03-09 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "9f3b4c2d1a0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        """
        UPDATE post_details
        SET body_text = left(body_text, 2048)
        WHERE char_length(body_text) > 2048
        """
    )
    op.execute(
        """
        ALTER TABLE post_details
        DROP CONSTRAINT IF EXISTS ck_post_details_body_text_max_length
        """
    )
    op.execute(
        """
        ALTER TABLE post_details
        ADD CONSTRAINT ck_post_details_body_text_max_length
        CHECK (char_length(body_text) <= 2048)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "ck_post_details_body_text_max_length",
        "post_details",
        type_="check",
    )
