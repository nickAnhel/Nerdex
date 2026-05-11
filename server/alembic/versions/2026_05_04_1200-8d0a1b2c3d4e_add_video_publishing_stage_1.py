"""add video publishing stage 1

Revision ID: 8d0a1b2c3d4e
Revises: f1a2b3c4d5e6
Create Date: 2026-05-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8d0a1b2c3d4e"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


video_orientation_enum = postgresql.ENUM(
    "landscape",
    "portrait",
    "square",
    name="video_orientation_enum",
    create_type=False,
)
video_processing_status_enum = postgresql.ENUM(
    "pending_upload",
    "uploaded",
    "metadata_extracting",
    "transcoding",
    "ready",
    "failed",
    name="video_processing_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    video_orientation_enum.create(bind, checkfirst=True)
    video_processing_status_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE asset_variant_type_enum ADD VALUE IF NOT EXISTS 'video_480p'")
    op.execute("ALTER TYPE asset_variant_type_enum ADD VALUE IF NOT EXISTS 'video_360p'")

    op.create_table(
        "video_playback_details",
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("orientation", video_orientation_enum, nullable=True),
        sa.Column(
            "processing_status",
            video_processing_status_enum,
            nullable=False,
            server_default=sa.text("'pending_upload'"),
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "available_quality_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )
    op.create_table(
        "video_details",
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "chapters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("publish_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_id"], ["content.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )


def downgrade() -> None:
    op.drop_table("video_details")
    op.drop_table("video_playback_details")
    bind = op.get_bind()
    video_processing_status_enum.drop(bind, checkfirst=True)
    video_orientation_enum.drop(bind, checkfirst=True)
