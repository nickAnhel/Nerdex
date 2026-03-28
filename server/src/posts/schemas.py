import datetime
import uuid

from pydantic import Field

from src.assets.enums import AttachmentTypeEnum, AssetTypeEnum
from src.common.schemas import BaseSchema
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostWriteStatus, PostWriteVisibility
from src.tags.schemas import TagGet
from src.users.schemas import UserGet


class PostAttachmentWrite(BaseSchema):
    asset_id: uuid.UUID
    attachment_type: AttachmentTypeEnum
    position: int = Field(ge=0)


class PostAttachmentGet(BaseSchema):
    asset_id: uuid.UUID
    attachment_type: AttachmentTypeEnum
    position: int = Field(ge=0)
    asset_type: AssetTypeEnum
    mime_type: str | None = None
    file_kind: str
    original_filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    preview_url: str | None = None
    original_url: str | None = None
    poster_url: str | None = None
    download_url: str | None = None
    stream_url: str | None = None
    is_audio: bool = False


class PostCreate(BaseSchema):
    content: str = Field(default="", max_length=2048)
    status: PostWriteStatus = PostWriteStatus.PUBLISHED
    visibility: PostWriteVisibility = PostWriteVisibility.PUBLIC
    tags: list[str] | None = None
    attachments: list[PostAttachmentWrite] = Field(default_factory=list)


class PostUpdate(BaseSchema):
    content: str | None = Field(default=None, max_length=2048)
    status: PostWriteStatus | None = None
    visibility: PostWriteVisibility | None = None
    tags: list[str] | None = None
    attachments: list[PostAttachmentWrite] | None = None


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
    comments_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    user: UserGet
    tags: list[TagGet] = Field(default_factory=list)
    media_attachments: list[PostAttachmentGet] = Field(default_factory=list)
    file_attachments: list[PostAttachmentGet] = Field(default_factory=list)
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool


class PostRating(BaseSchema):
    post_id: uuid.UUID
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None
