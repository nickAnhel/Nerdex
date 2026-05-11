import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
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

    messages: Mapped[list["MessageModel"]] = relationship(back_populates="chat")
    events: Mapped[list["EventModel"]] = relationship(back_populates="chat")

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
