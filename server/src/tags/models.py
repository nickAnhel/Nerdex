from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base


class TagModel(Base):
    __tablename__ = "tags"

    tag_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )

    content_tags: Mapped[list["ContentTagModel"]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="contents,tags",
    )
    contents: Mapped[list["ContentModel"]] = relationship(  # type: ignore[name-defined]
        secondary="content_tags",
        back_populates="tags",
        passive_deletes=True,
        overlaps="content_tags,tag,content",
    )


class ContentTagModel(Base):
    __tablename__ = "content_tags"
    __table_args__ = (Index("ix_content_tags_tag_id", "tag_id"),)

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.tag_id", ondelete="CASCADE"),
        primary_key=True,
    )

    content: Mapped["ContentModel"] = relationship(  # type: ignore[name-defined]
        back_populates="content_tags",
        passive_deletes=True,
        overlaps="contents,tags",
    )
    tag: Mapped[TagModel] = relationship(
        back_populates="content_tags",
        passive_deletes=True,
        overlaps="contents,tags",
    )
