from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.enums import ReactionTypeEnum


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class CommentModel(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("depth BETWEEN 0 AND 2", name="ck_comments_depth_range"),
        CheckConstraint(
            "char_length(body_text) <= 2048",
            name="ck_comments_body_text_max_length",
        ),
        Index(
            "ix_comments_content_parent_created_at_desc",
            "content_id",
            "parent_comment_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_comments_root_parent_created_at_asc",
            "root_comment_id",
            "parent_comment_id",
            text("created_at ASC"),
        ),
        Index("ix_comments_author_id", "author_id"),
    )

    comment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="CASCADE"),
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
    )
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    root_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    reply_to_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(Integer)
    body_text: Mapped[str] = mapped_column(String(2048))
    replies_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    likes_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    dislikes_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
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

    content: Mapped["ContentModel"] = relationship(  # type: ignore[name-defined]
        back_populates="comments",
        passive_deletes=True,
    )
    author: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="comments",
        passive_deletes=True,
    )
    parent_comment: Mapped["CommentModel | None"] = relationship(
        back_populates="replies",
        foreign_keys=[parent_comment_id],
        remote_side=lambda: [CommentModel.comment_id],
        passive_deletes=True,
    )
    replies: Mapped[list["CommentModel"]] = relationship(
        back_populates="parent_comment",
        foreign_keys="CommentModel.parent_comment_id",
        passive_deletes=True,
    )
    root_comment: Mapped["CommentModel | None"] = relationship(
        foreign_keys=[root_comment_id],
        remote_side=lambda: [CommentModel.comment_id],
        passive_deletes=True,
    )
    reply_to_comment: Mapped["CommentModel | None"] = relationship(
        foreign_keys=[reply_to_comment_id],
        remote_side=lambda: [CommentModel.comment_id],
        passive_deletes=True,
    )
    reactions: Mapped[list["CommentReactionModel"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CommentReactionModel(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (Index("ix_comment_reactions_user_id", "user_id"),)

    comment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
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

    comment: Mapped[CommentModel] = relationship(back_populates="reactions")
    user: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="comment_reactions",
        passive_deletes=True,
    )
