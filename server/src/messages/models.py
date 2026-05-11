import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.models import Base


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "client_message_id",
            name="uq_messages_chat_user_client_message_id",
        ),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    content: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"))
    chat: Mapped["ChatModel"] = relationship(back_populates="messages")

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    user: Mapped["UserModel"] = relationship(back_populates="messages")
    asset_links: Mapped[list["MessageAssetModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def content_ellipsis(self) -> str:
        if len(self.content) < 100:
            return self.content

        return " ".join(self.content.split()[:5]) + "..."
