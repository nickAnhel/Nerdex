import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class EventModel(Base):
    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    user: Mapped["UserModel"] = relationship(
        back_populates="events",
        foreign_keys=[user_id],
    )

    altered_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    altered_user: Mapped["UserModel"] = relationship(
        back_populates="altered_events",
        foreign_keys=[altered_user_id],
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.chat_id", ondelete="CASCADE")
    )
    chat: Mapped["ChatModel"] = relationship(back_populates="events")
