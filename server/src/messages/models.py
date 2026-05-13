import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base
from src.content.enums import ReactionTypeEnum


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "client_message_id",
            name="uq_messages_chat_user_client_message_id",
        ),
        Index("ix_messages_chat_created_at", "chat_id", "created_at"),
        Index("ix_messages_chat_reply_to_message_id", "chat_id", "reply_to_message_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    content: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    edited_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"))
    chat: Mapped["ChatModel"] = relationship(back_populates="messages")
    timeline_item: Mapped["ChatTimelineItemModel | None"] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    user: Mapped["UserModel"] = relationship(
        back_populates="messages",
        foreign_keys=[user_id],
    )
    reactions: Mapped[list["MessageReactionModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reply_to_message: Mapped["MessageModel | None"] = relationship(
        "MessageModel",
        remote_side=[message_id],
        foreign_keys=[reply_to_message_id],
    )
    asset_links: Mapped[list["MessageAssetModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    shared_content: Mapped["MessageSharedContentModel | None"] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    @property
    def content_ellipsis(self) -> str:
        if len(self.content) < 100:
            return self.content

        return " ".join(self.content.split()[:5]) + "..."


class MessageSharedContentModel(Base):
    __tablename__ = "message_shared_content"
    __table_args__ = (
        Index("ix_message_shared_content_content_id", "content_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.content_id", ondelete="RESTRICT"),
    )

    message: Mapped[MessageModel] = relationship(back_populates="shared_content")
    content: Mapped["ContentModel"] = relationship()  # type: ignore[name-defined]


class MessageReactionModel(Base):
    __tablename__ = "message_reactions"
    __table_args__ = (Index("ix_message_reactions_user_id", "user_id"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
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
        server_default=func.now(),
    )

    message: Mapped[MessageModel] = relationship(back_populates="reactions")
    user: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        back_populates="message_reactions",
        passive_deletes=True,
    )
