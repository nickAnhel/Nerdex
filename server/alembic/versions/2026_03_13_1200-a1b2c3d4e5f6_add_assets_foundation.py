"""add assets foundation

Revision ID: a1b2c3d4e5f6
Revises: e7f8a9b0c1d2
Create Date: 2026-03-13 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


asset_type_enum = postgresql.ENUM("image", "video", "file", name="asset_type_enum", create_type=False)
asset_status_enum = postgresql.ENUM(
    "pending_upload",
    "uploaded",
    "processing",
    "ready",
    "failed",
    "deleted",
    name="asset_status_enum",
    create_type=False,
)
asset_access_type_enum = postgresql.ENUM(
    "private",
    "public",
    "inherited",
    name="asset_access_type_enum",
    create_type=False,
)
asset_variant_status_enum = postgresql.ENUM(
    "pending",
    "ready",
    "failed",
    "deleted",
    name="asset_variant_status_enum",
    create_type=False,
)
asset_variant_type_enum = postgresql.ENUM(
    "original",
    "avatar_medium",
    "avatar_small",
    "image_medium",
    "image_small",
    "video_preview_original",
    "video_preview_medium",
    "video_preview_small",
    "video_720p",
    "video_1080p",
    name="asset_variant_type_enum",
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
    asset_type_enum.create(bind, checkfirst=True)
    asset_status_enum.create(bind, checkfirst=True)
    asset_access_type_enum.create(bind, checkfirst=True)
    asset_variant_status_enum.create(bind, checkfirst=True)
    asset_variant_type_enum.create(bind, checkfirst=True)
    content_asset_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "assets",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type", asset_type_enum, nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("original_extension", sa.String(length=32), nullable=True),
        sa.Column("declared_mime_type", sa.String(length=255), nullable=True),
        sa.Column("detected_mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", asset_status_enum, nullable=False),
        sa.Column("access_type", asset_access_type_enum, nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index("ix_assets_owner_id", "assets", ["owner_id"], unique=False)
    op.create_index("ix_assets_status", "assets", ["status"], unique=False)
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"], unique=False)

    op.create_table(
        "asset_variants",
        sa.Column("asset_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_variant_type", asset_variant_type_enum, nullable=False),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", asset_variant_status_enum, nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_variant_id"),
        sa.UniqueConstraint("asset_id", "asset_variant_type", name="uq_asset_variants_asset_type"),
        sa.UniqueConstraint("storage_bucket", "storage_key", name="uq_asset_variants_bucket_key"),
    )
    op.create_index(
        "ix_asset_variants_asset_id_status",
        "asset_variants",
        ["asset_id", "status"],
        unique=False,
    )

    op.create_table(
        "content_asset",
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_asset_type", content_asset_type_enum, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("placement_key", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "asset_id", "content_asset_type"),
    )
    op.create_index(
        "ix_content_asset_content_type_sort",
        "content_asset",
        ["content_id", "content_asset_type", "sort_order"],
        unique=False,
    )
    op.create_index("ix_content_asset_asset_id", "content_asset", ["asset_id"], unique=False)

    op.create_table(
        "message_asset",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.message_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", "asset_id"),
    )
    op.create_index("ix_message_asset_message_sort", "message_asset", ["message_id", "sort_order"], unique=False)
    op.create_index("ix_message_asset_asset_id", "message_asset", ["asset_id"], unique=False)

    op.add_column("users", sa.Column("avatar_asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_users_avatar_asset_id_assets",
        "users",
        "assets",
        ["avatar_asset_id"],
        ["asset_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_avatar_asset_id_assets", "users", type_="foreignkey")
    op.drop_column("users", "avatar_asset_id")

    op.drop_index("ix_message_asset_asset_id", table_name="message_asset")
    op.drop_index("ix_message_asset_message_sort", table_name="message_asset")
    op.drop_table("message_asset")

    op.drop_index("ix_content_asset_asset_id", table_name="content_asset")
    op.drop_index("ix_content_asset_content_type_sort", table_name="content_asset")
    op.drop_table("content_asset")

    op.drop_index("ix_asset_variants_asset_id_status", table_name="asset_variants")
    op.drop_table("asset_variants")

    op.drop_index("ix_assets_asset_type", table_name="assets")
    op.drop_index("ix_assets_status", table_name="assets")
    op.drop_index("ix_assets_owner_id", table_name="assets")
    op.drop_table("assets")

    bind = op.get_bind()
    content_asset_type_enum.drop(bind, checkfirst=True)
    asset_variant_type_enum.drop(bind, checkfirst=True)
    asset_variant_status_enum.drop(bind, checkfirst=True)
    asset_access_type_enum.drop(bind, checkfirst=True)
    asset_status_enum.drop(bind, checkfirst=True)
    asset_type_enum.drop(bind, checkfirst=True)
