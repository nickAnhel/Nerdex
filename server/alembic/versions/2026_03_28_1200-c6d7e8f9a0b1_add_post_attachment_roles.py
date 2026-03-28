"""add post attachment roles

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-03-28 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


attachment_type_enum = postgresql.ENUM(
    "media",
    "file",
    "cover",
    "inline",
    "video_source",
    "video_preview",
    "thumbnail",
    name="attachment_type_enum",
    create_type=False,
)
content_asset_type_enum = postgresql.ENUM(
    "attachment",
    "cover",
    "inline",
    "video_source",
    "video_preview",
    "thumbnail",
    name="content_asset_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    attachment_type_enum.create(bind, checkfirst=True)

    op.add_column("content_asset", sa.Column("attachment_type", attachment_type_enum, nullable=True))
    op.add_column(
        "content_asset",
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.execute(
        """
        UPDATE content_asset AS ca
        SET attachment_type = CASE
            WHEN ca.content_asset_type::text = 'attachment' THEN CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM assets AS a
                    WHERE a.asset_id = ca.asset_id
                      AND a.asset_type IN ('image', 'video')
                ) THEN 'media'::attachment_type_enum
                ELSE 'file'::attachment_type_enum
            END
            ELSE ca.content_asset_type::text::attachment_type_enum
        END
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                ca.content_id,
                ca.asset_id,
                ca.attachment_type,
                ROW_NUMBER() OVER (
                    PARTITION BY ca.content_id, ca.attachment_type
                    ORDER BY COALESCE(ca.sort_order, 0), ca.created_at, ca.asset_id
                ) - 1 AS next_position
            FROM content_asset AS ca
        )
        UPDATE content_asset AS ca
        SET position = ranked.next_position
        FROM ranked
        WHERE ca.content_id = ranked.content_id
          AND ca.asset_id = ranked.asset_id
          AND ca.attachment_type = ranked.attachment_type
        """
    )

    op.drop_index("ix_content_asset_content_type_sort", table_name="content_asset")
    op.drop_constraint("content_asset_pkey", "content_asset", type_="primary")
    op.drop_column("content_asset", "content_asset_type")
    op.drop_column("content_asset", "sort_order")

    op.alter_column("content_asset", "attachment_type", nullable=False)
    op.create_primary_key("content_asset_pkey", "content_asset", ["content_id", "asset_id", "attachment_type"])
    op.create_unique_constraint(
        "uq_content_asset_content_attachment_position",
        "content_asset",
        ["content_id", "attachment_type", "position"],
    )
    op.create_check_constraint(
        "ck_content_asset_position_non_negative",
        "content_asset",
        "position >= 0",
    )
    op.create_index(
        "ix_content_asset_content_attachment_position",
        "content_asset",
        ["content_id", "attachment_type", "position"],
        unique=False,
    )

    content_asset_type_enum.drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    content_asset_type_enum.create(bind, checkfirst=True)

    op.add_column("content_asset", sa.Column("content_asset_type", content_asset_type_enum, nullable=True))
    op.add_column(
        "content_asset",
        sa.Column("sort_order", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE content_asset
        SET content_asset_type = CASE
            WHEN attachment_type::text IN ('media', 'file') THEN 'attachment'::content_asset_type_enum
            ELSE attachment_type::text::content_asset_type_enum
        END,
        sort_order = position
        """
    )

    op.drop_index("ix_content_asset_content_attachment_position", table_name="content_asset")
    op.drop_constraint("ck_content_asset_position_non_negative", "content_asset", type_="check")
    op.drop_constraint("uq_content_asset_content_attachment_position", "content_asset", type_="unique")
    op.drop_constraint("content_asset_pkey", "content_asset", type_="primary")

    op.drop_column("content_asset", "attachment_type")
    op.drop_column("content_asset", "position")
    op.alter_column("content_asset", "content_asset_type", nullable=False)

    op.create_primary_key("content_asset_pkey", "content_asset", ["content_id", "asset_id", "content_asset_type"])
    op.create_index(
        "ix_content_asset_content_type_sort",
        "content_asset",
        ["content_id", "content_asset_type", "sort_order"],
        unique=False,
    )

    attachment_type_enum.drop(bind, checkfirst=True)
