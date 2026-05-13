import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.chats.enums import ChatMemberRole, ChatType
from src.common.models import Base


class ChatModel(Base):
    __tablename__ = "chats"
    __table_args__ = (
        CheckConstraint(
            "chat_type in ('direct', 'group')",
            name="ck_chats_chat_type",
        ),
        Index(
            "uq_chats_direct_key",
            "direct_key",
            unique=True,
            postgresql_where=text("direct_key IS NOT NULL"),
        ),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str]
    is_private: Mapped[bool] = mapped_column(default=False)
    chat_type: Mapped[str] = mapped_column(default=ChatType.GROUP.value)
    direct_key: Mapped[str | None] = mapped_column(nullable=True)
    last_timeline_seq: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default=text("0"),
    )

    messages: Mapped[list["MessageModel"]] = relationship(back_populates="chat")
    events: Mapped[list["EventModel"]] = relationship(back_populates="chat")
    timeline_items: Mapped[list["ChatTimelineItemModel"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    owner: Mapped["UserModel"] = relationship(back_populates="created_chats")

    members: Mapped[list["UserModel"]] = relationship(
        back_populates="joined_chats",
        secondary="chat_user",
    )


class MembershipModel(Base):
    __tablename__ = "chat_user"
    __table_args__ = (
        CheckConstraint(
            "role in ('owner', 'member')",
            name="ck_chat_user_role",
        ),
        Index("ix_chat_user_user_id", "user_id"),
        Index("ix_chat_user_last_read_message_id", "last_read_message_id"),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(default=ChatMemberRole.MEMBER.value)
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_muted: Mapped[bool] = mapped_column(default=False)


class ChatTimelineItemModel(Base):
    __tablename__ = "chat_timeline_items"
    __table_args__ = (
        CheckConstraint(
            "item_type in ('message', 'event')",
            name="ck_chat_timeline_items_item_type",
        ),
        CheckConstraint(
            """
            (
                item_type = 'message'
                and message_id is not null
                and event_id is null
            )
            or
            (
                item_type = 'event'
                and event_id is not null
                and message_id is null
            )
            """,
            name="ck_chat_timeline_items_single_ref",
        ),
        UniqueConstraint("message_id", name="uq_chat_timeline_items_message_id"),
        UniqueConstraint("event_id", name="uq_chat_timeline_items_event_id"),
        Index("ix_chat_timeline_items_chat_seq", "chat_id", "chat_seq"),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    chat_seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_type: Mapped[str]
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        nullable=True,
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.event_id", ondelete="CASCADE"),
        nullable=True,
    )

    chat: Mapped["ChatModel"] = relationship(back_populates="timeline_items")
    message: Mapped["MessageModel | None"] = relationship(back_populates="timeline_item")
    event: Mapped["EventModel | None"] = relationship(back_populates="timeline_item")
