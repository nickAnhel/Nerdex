import uuid
import datetime

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class PostModel(Base):
    __tablename__ = "posts"

    post_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    content: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    user: Mapped["UserModel"] = relationship(back_populates="created_posts")  # type: ignore
