import datetime
import uuid

from pydantic import Field

from src.common.schemas import BaseSchema
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostWriteStatus, PostWriteVisibility
from src.users.schemas import UserGet


class PostCreate(BaseSchema):
    content: str = Field(min_length=1, max_length=2048)
    status: PostWriteStatus = PostWriteStatus.PUBLISHED
    visibility: PostWriteVisibility = PostWriteVisibility.PUBLIC


class PostUpdate(BaseSchema):
    content: str | None = Field(default=None, min_length=1, max_length=2048)
    status: PostWriteStatus | None = None
    visibility: PostWriteVisibility | None = None


class PostGet(BaseSchema):
    post_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    user: UserGet
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool


class PostRating(BaseSchema):
    post_id: uuid.UUID
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None
