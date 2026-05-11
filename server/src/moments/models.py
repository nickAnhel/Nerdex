from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.models import ContentModel


class MomentDetailsModel(Base):
    __tablename__ = "moment_details"
    __table_args__ = (
        CheckConstraint("char_length(caption) <= 2200", name="ck_moment_details_caption_length"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    caption: Mapped[str] = mapped_column(String(2200), default="", server_default=text("''"))
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
        back_populates="moment_details",
        passive_deletes=True,
    )
