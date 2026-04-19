from __future__ import annotations

import datetime
import typing as tp
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.assets.enums import (
    AttachmentTypeEnum,
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
)
from src.common.models import Base


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class AssetModel(Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_owner_id", "owner_id"),
        Index("ix_assets_status", "status"),
        Index("ix_assets_asset_type", "asset_type"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
    )
    asset_type: Mapped[AssetTypeEnum] = mapped_column(
        Enum(AssetTypeEnum, name="asset_type_enum", values_callable=_enum_values),
    )
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_extension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    declared_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[AssetStatusEnum] = mapped_column(
        Enum(AssetStatusEnum, name="asset_status_enum", values_callable=_enum_values),
    )
    access_type: Mapped[AssetAccessTypeEnum] = mapped_column(
        Enum(AssetAccessTypeEnum, name="asset_access_type_enum", values_callable=_enum_values),
    )
    asset_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    owner: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="owned_assets",
        foreign_keys=[owner_id],
    )
    variants: Mapped[list["AssetVariantModel"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AssetVariantModel.created_at",
    )
    content_links: Mapped[list["ContentAssetModel"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    message_links: Mapped[list["MessageAssetModel"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    avatar_for_users: Mapped[list["UserModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="avatar_asset",
        foreign_keys="UserModel.avatar_asset_id",
    )


class AssetVariantModel(Base):
    __tablename__ = "asset_variants"
    __table_args__ = (
        UniqueConstraint("asset_id", "asset_variant_type", name="uq_asset_variants_asset_type"),
        UniqueConstraint("storage_bucket", "storage_key", name="uq_asset_variants_bucket_key"),
        Index("ix_asset_variants_asset_id_status", "asset_id", "status"),
    )

    asset_variant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
    )
    asset_variant_type: Mapped[AssetVariantTypeEnum] = mapped_column(
        Enum(AssetVariantTypeEnum, name="asset_variant_type_enum", values_callable=_enum_values),
    )
    storage_bucket: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column()
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    status: Mapped[AssetVariantStatusEnum] = mapped_column(
        Enum(AssetVariantStatusEnum, name="asset_variant_status_enum", values_callable=_enum_values),
    )
    variant_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )

    asset: Mapped[AssetModel] = relationship(back_populates="variants")


class ContentAssetModel(Base):
    __tablename__ = "content_asset"
    __table_args__ = (
        UniqueConstraint(
            "content_id",
            "attachment_type",
            "position",
            name="uq_content_asset_content_attachment_position",
        ),
        CheckConstraint("position >= 0", name="ck_content_asset_position_non_negative"),
        Index("ix_content_asset_content_attachment_position", "content_id", "attachment_type", "position"),
        Index("ix_content_asset_asset_id", "asset_id"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        primary_key=True,
    )
    attachment_type: Mapped[AttachmentTypeEnum] = mapped_column(
        Enum(AttachmentTypeEnum, name="attachment_type_enum", values_callable=_enum_values),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    placement_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    link_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    content: Mapped["ContentModel"] = relationship(  # type: ignore[name-defined]
        back_populates="asset_links",
    )
    asset: Mapped[AssetModel] = relationship(back_populates="content_links")


class MessageAdessetModel(Base):
    __tablename__ = "message_asset"
    __table_args__ = (
        Index("ix_message_asset_message_sort", "message_id", "sort_order"),
        Index("ix_message_asset_asset_id", "asset_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    link_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    message: Mapped["MessageModel"] = relationship(  # type: ignore[name-defined]
        back_populates="asset_links",
    )
    asset: Mapped[AssetModel] = relationship(back_populates="message_links")
