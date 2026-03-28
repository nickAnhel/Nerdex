import typing as tp
import uuid

from pydantic import Field

from src.common.schemas import BaseSchema

type Username = tp.Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")]


class UserCreate(BaseSchema):
    username: str = Field(max_length=32)
    password: str = Field(min_length=8, max_length=50)


class UserAvatarCrop(BaseSchema):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    size: float = Field(gt=0, le=1)


class UserAvatarGet(BaseSchema):
    small_url: str | None = None
    medium_url: str | None = None
    crop: UserAvatarCrop


class UserAvatarUpdate(BaseSchema):
    asset_id: uuid.UUID
    crop: UserAvatarCrop


class UserGet(BaseSchema):
    user_id: uuid.UUID
    avatar_asset_id: uuid.UUID | None = None
    avatar: UserAvatarGet | None = None
    username: Username
    is_admin: bool
    subscribers_count: int

    is_subscribed: bool | None = None


class UserGetWithPassword(UserGet):
    hashed_password: str


class UserUpdate(BaseSchema):
    username: Username | None = Field(max_length=32, default=None)
