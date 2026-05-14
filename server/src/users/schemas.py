import typing as tp
import uuid

from pydantic import Field, HttpUrl

from src.common.schemas import BaseSchema

type Username = tp.Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")]
type DisplayName = tp.Annotated[str, Field(min_length=1, max_length=64)]
type Bio = tp.Annotated[str, Field(max_length=500)]
type LinkLabel = tp.Annotated[str, Field(min_length=1, max_length=32)]


class UserLink(BaseSchema):
    label: LinkLabel
    url: HttpUrl


class UserCreate(BaseSchema):
    username: Username = Field(max_length=32)
    password: str = Field(min_length=8, max_length=50)
    display_name: DisplayName | None = None
    bio: Bio | None = None
    links: list[UserLink] = Field(default_factory=list)


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
    display_name: str = ""
    bio: str | None = None
    links: list[UserLink] = Field(default_factory=list)
    is_admin: bool
    subscribers_count: int

    is_subscribed: bool | None = None


class UserGetWithPassword(BaseSchema):
    user_id: uuid.UUID
    username: Username
    is_admin: bool
    hashed_password: str


class UserUpdate(BaseSchema):
    username: Username | None = Field(max_length=32, default=None)
    display_name: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=500)
    links: list[UserLink] | None = None


class UserProfileUpdate(UserUpdate):
    pass


class UserPasswordUpdate(BaseSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=50)
