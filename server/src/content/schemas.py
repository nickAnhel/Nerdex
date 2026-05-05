import datetime
import uuid

from pydantic import Field

from src.articles.schemas import ArticleAssetGet
from src.common.schemas import BaseSchema
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.schemas import PostAttachmentGet
from src.tags.schemas import TagGet
from src.users.schemas import UserGet
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum
from src.videos.schemas import VideoAssetGet


class ContentListItemGet(BaseSchema):
    content_id: uuid.UUID
    content_type: ContentTypeEnum
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    comments_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    user: UserGet
    tags: list[TagGet] = Field(default_factory=list)
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool

    post_content: str | None = None
    media_attachments: list[PostAttachmentGet] = Field(default_factory=list)
    file_attachments: list[PostAttachmentGet] = Field(default_factory=list)

    title: str | None = None
    excerpt: str | None = None
    slug: str | None = None
    canonical_path: str | None = None
    reading_time_minutes: int | None = None
    word_count: int | None = None
    cover: ArticleAssetGet | VideoAssetGet | None = None

    description: str | None = None
    duration_seconds: int | None = None
    orientation: VideoOrientationEnum | None = None
    processing_status: VideoProcessingStatusEnum | None = None
    processing_error: str | None = None
