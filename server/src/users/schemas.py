import typing as tp
import uuid

from pydantic import Field

from src.schemas import BaseSchema

type Username = tp.Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")]


class UserCreate(BaseSchema):
    username: str = Field(max_length=32)
    password: str = Field(min_length=8, max_length=50)


class UserGet(BaseSchema):
    user_id: uuid.UUID
    username: Username
    is_admin: bool
    subscribers_count: int

    is_subscribed: bool | None = None


class UserGetWithPassword(UserGet):
    hashed_password: str


class UserUpdate(BaseSchema):
    username: Username | None = Field(max_length=32, default=None)
