from __future__ import annotations

import datetime
import typing as tp
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.enums import (
    ContentStatusEnum,
    ContentTypeEnum,
    ContentVisibilityEnum,
    ReactionTypeEnum,
)
from src.tags.models import ContentTagModel, TagModel


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class ContentModel(Base):
    __tablename__ = "content"
    __table_args__ = (
        Index("ix_content_author_id", "author_id"),
        Index("ix_content_status_visibility_published_at", "status", "visibility", text("published_at DESC")),
        Index("ix_content_type_status_published_at", "content_type", "status", text("published_at DESC")),
        Index("ix_content_author_status_visibility_created_at", "author_id", "status", "visibility", text("created_at DESC")),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
    )
    content_type: Mapped[ContentTypeEnum] = mapped_column(
        Enum(ContentTypeEnum, name="content_type_enum", values_callable=_enum_values),
    )
    status: Mapped[ContentStatusEnum] = mapped_column(
        Enum(ContentStatusEnum, name="content_status_enum", values_callable=_enum_values),
    )
    visibility: Mapped[ContentVisibilityEnum] = mapped_column(
        Enum(ContentVisibilityEnum, name="content_visibility_enum", values_callable=_enum_values),
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    published_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    comments_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    likes_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    dislikes_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    content_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    author: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="created_posts",
        passive_deletes=True,
    )
    post_details: Mapped["PostDetailsModel"] = relationship(  # type: ignore[name-defined]
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    comments: Mapped[list["CommentModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reactions: Mapped[list["ContentReactionModel"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    content_tags: Mapped[list[ContentTagModel]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="contents,tags",
    )
    tags: Mapped[list[TagModel]] = relationship(
        secondary="content_tags",
        back_populates="contents",
        passive_deletes=True,
        order_by="TagModel.slug",
        overlaps="content_tags,tag,content",
    )

    @property
    def post_id(self) -> uuid.UUID:
        return self.content_id

    @property
    def user_id(self) -> uuid.UUID:
        return self.author_id

    @property
    def user(self):  # type: ignore[no-untyped-def]
        return self.author

    @property
    def content(self) -> str:
        return self.post_details.body_text

    @property
    def content_body_ellipsis(self) -> str:
        content = self.post_details.body_text
        if len(content) < 100:
            return content

        return " ".join(content.split()[:5]) + "..."


class ContentReactionModel(Base):
    __tablename__ = "content_reactions"
    __table_args__ = (Index("ix_content_reactions_user_id", "user_id"),)

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    reaction_type: Mapped[ReactionTypeEnum] = mapped_column(
        Enum(ReactionTypeEnum, name="reaction_type_enum", values_callable=_enum_values),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
    )

    content: Mapped[ContentModel] = relationship(back_populates="reactions")
    user: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="content_reactions",
        passive_deletes=True,
    )
