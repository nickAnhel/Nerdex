from __future__ import annotations

import datetime
import typing as tp
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.models import ContentModel
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class VideoPlaybackDetailsModel(Base):
    __tablename__ = "video_playback_details"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[VideoOrientationEnum | None] = mapped_column(
        Enum(VideoOrientationEnum, name="video_orientation_enum", values_callable=_enum_values),
        nullable=True,
    )
    processing_status: Mapped[VideoProcessingStatusEnum] = mapped_column(
        Enum(VideoProcessingStatusEnum, name="video_processing_status_enum", values_callable=_enum_values),
        default=VideoProcessingStatusEnum.PENDING_UPLOAD,
        server_default=text("'pending_upload'"),
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_quality_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        JSONB,
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

    content: Mapped[ContentModel] = relationship(
        back_populates="video_playback_details",
        passive_deletes=True,
    )


class VideoDetailsModel(Base):
    __tablename__ = "video_details"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    chapters: Mapped[list[dict[str, tp.Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    publish_requested_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    content: Mapped[ContentModel] = relationship(
        back_populates="video_details",
        passive_deletes=True,
    )
