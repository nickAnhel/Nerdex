import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class MessageModel(Base):
    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"))
    chat: Mapped["ChatModel"] = relationship(back_populates="messages")

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    user: Mapped["UserModel"] = relationship(back_populates="messages")

    @property
    def content_ellipsis(self) -> str:
        if len(self.content) < 100:
            return self.content

        return " ".join(self.content.split()[:5]) + "..."
