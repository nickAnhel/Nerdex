from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.models import ContentModel


class PostDetailsModel(Base):
    __tablename__ = "post_details"
    __table_args__ = (
        CheckConstraint("char_length(body_text) <= 2048", name="ck_post_details_body_text_max_length"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    body_text: Mapped[str] = mapped_column(Text)

    content: Mapped[ContentModel] = relationship(
        back_populates="post_details",
        passive_deletes=True,
    )
