import uuid

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


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

    is_admin: Mapped[bool] = mapped_column(default=False)

    created_posts: Mapped[list["PostModel"]] = relationship(  # type: ignore
        back_populates="user",
    )
    liked_posts: Mapped["PostModel"] = relationship(  # type: ignore
        back_populates="liked_users",
        secondary="user_post_likes",
    )
    disliked_posts: Mapped["PostModel"] = relationship(  # type: ignore
        back_populates="disliked_users",
        secondary="user_post_dislikes",
    )
