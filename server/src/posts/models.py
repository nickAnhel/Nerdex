import uuid
import datetime

from sqlalchemy import ForeignKey, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class PostModel(Base):
    __tablename__ = "posts"

    post_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    content: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    likes: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    dislikes: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    user: Mapped["UserModel"] = relationship(  # type: ignore
        back_populates="created_posts", passive_deletes=True
    )

    liked_users: Mapped["UserModel"] = relationship(  # type: ignore
        back_populates="liked_posts",
        secondary="user_post_likes",
    )
    disliked_users: Mapped["UserModel"] = relationship(  # type: ignore
        back_populates="disliked_posts",
        secondary="user_post_dislikes",
    )

    @property
    def content_ellipsis(self) -> str:
        if len(self.content) < 100:
            return self.content

        return " ".join(self.content.split()[:5]) + "..."


class LikesModel(Base):
    __tablename__ = "user_post_likes"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class DislikesModel(Base):
    __tablename__ = "user_post_dislikes"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
