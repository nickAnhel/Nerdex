from uuid import UUID

from pydantic import Field

from src.schemas import BaseSchema


class UserCreate(BaseSchema):
    username: str = Field(max_length=32)
    password: str = Field(min_length=8, max_length=50)


class UserGet(BaseSchema):
    user_id: UUID
    username: str
    is_admin: bool


class UserGetWithPassword(UserGet):
    hashed_password: str


class UserUpdate(BaseSchema):
    username: str | None = Field(max_length=32, default=None)
