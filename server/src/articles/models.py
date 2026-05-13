from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.models import ContentModel


class ArticleDetailsModel(Base):
    __tablename__ = "article_details"
    __table_args__ = (
        CheckConstraint("char_length(slug) BETWEEN 1 AND 180", name="ck_article_details_slug_length"),
        CheckConstraint("word_count >= 0", name="ck_article_details_word_count_non_negative"),
        CheckConstraint(
            "reading_time_minutes >= 1",
            name="ck_article_details_reading_time_minutes_positive",
        ),
        Index("ix_article_details_slug", "slug"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    slug: Mapped[str] = mapped_column(String(180))
    body_markdown: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    word_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    toc: Mapped[list[dict[str, str | int]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))

    content: Mapped[ContentModel] = relationship(
        back_populates="article_details",
        passive_deletes=True,
    )
