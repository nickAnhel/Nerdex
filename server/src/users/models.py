import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"

    subscriber_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    subscribed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "users_username_trgm_idx",
            "username",
            postgresql_using="gin",
            postgresql_ops={"username": "gin_trgm_ops"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    username: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]

    subscribers_count: Mapped[int] = mapped_column(default=0)

    is_admin: Mapped[bool] = mapped_column(default=False)

    created_posts: Mapped[list["PostModel"]] = relationship(  # type: ignore
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    liked_posts: Mapped["PostModel"] = relationship(  # type: ignore
        back_populates="liked_users",
        secondary="user_post_likes",
    )
    disliked_posts: Mapped["PostModel"] = relationship(  # type: ignore
        back_populates="disliked_users",
        secondary="user_post_dislikes",
    )
    created_chats: Mapped[list["ChatModel"]] = relationship(  # type: ignore
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    joined_chats: Mapped[list["ChatModel"]] = relationship(  # type: ignore
        back_populates="members",
        secondary="chat_user",
    )
    events: Mapped[list["EventModel"]] = relationship(  # type: ignore
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="EventModel.user_id",
    )
    altered_events: Mapped[list["EventModel"]] = relationship(  # type: ignore
        back_populates="altered_user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="EventModel.altered_user_id",
    )
    messages: Mapped[list["MessageModel"]] = relationship(  # type: ignore
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    subscribers: Mapped[list["UserModel"]] = relationship(
        back_populates="subscribed",
        secondary="subscriptions",
        primaryjoin=(user_id == SubscriptionModel.subscribed_id),
        secondaryjoin=(user_id == SubscriptionModel.subscriber_id),
    )
    subscribed: Mapped[list["UserModel"]] = relationship(
        back_populates="subscribers",
        secondary="subscriptions",
        primaryjoin=(user_id == SubscriptionModel.subscriber_id),
        secondaryjoin=(user_id == SubscriptionModel.subscribed_id),
    )
