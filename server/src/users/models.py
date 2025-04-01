import uuid

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    username: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]

    is_admin: Mapped[bool] = mapped_column(default=False)

    created_posts: Mapped[list["PostModel"]] = relationship(back_populates="user")  # type: ignore
