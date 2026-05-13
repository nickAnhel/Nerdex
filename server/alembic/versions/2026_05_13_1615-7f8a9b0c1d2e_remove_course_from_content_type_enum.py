"""Remove course from content_type_enum

Revision ID: 7f8a9b0c1d2e
Revises: 6e7b8c9d0e1f
Create Date: 2026-05-13 16:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7f8a9b0c1d2e"
down_revision: Union[str, None] = "6e7f8a9b0c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


content_type_enum_without_course = postgresql.ENUM(
    "post",
    "article",
    "video",
    "moment",
    name="content_type_enum_without_course",
    create_type=False,
)
content_type_enum_with_course = postgresql.ENUM(
    "post",
    "article",
    "video",
    "moment",
    "course",
    name="content_type_enum_with_course",
    create_type=False,
)


def upgrade() -> None:
    """Drop course from the content type enum."""

    bind = op.get_bind()
    content_type_enum_without_course.create(bind, checkfirst=True)

    op.execute(
        """
        DELETE FROM message_shared_content
        WHERE content_id IN (
            SELECT content_id
            FROM content
            WHERE content_type::text NOT IN ('post', 'article', 'video', 'moment')
        )
        """
    )
    op.execute(
        """
        DELETE FROM content
        WHERE content_type::text NOT IN ('post', 'article', 'video', 'moment')
        """
    )
    op.execute(
        """
        ALTER TABLE content
        ALTER COLUMN content_type TYPE content_type_enum_without_course
        USING content_type::text::content_type_enum_without_course
        """
    )
    op.execute("DROP TYPE content_type_enum")
    op.execute("ALTER TYPE content_type_enum_without_course RENAME TO content_type_enum")


def downgrade() -> None:
    """Restore course in the content type enum."""

    bind = op.get_bind()
    content_type_enum_with_course.create(bind, checkfirst=True)

    op.execute(
        """
        ALTER TABLE content
        ALTER COLUMN content_type TYPE content_type_enum_with_course
        USING content_type::text::content_type_enum_with_course
        """
    )
    op.execute("DROP TYPE content_type_enum")
    op.execute("ALTER TYPE content_type_enum_with_course RENAME TO content_type_enum")
