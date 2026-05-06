import datetime
import uuid

from pydantic import Field

from src.assets.enums import AttachmentTypeEnum, AssetStatusEnum, AssetTypeEnum
from src.assets.schemas import AssetVariantGet
from src.common.schemas import BaseSchema
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.tags.schemas import TagGet
from src.users.schemas import UserGet
from src.videos.enums import (
    VideoOrientationEnum,
    VideoProcessingStatusEnum,
    VideoWriteStatus,
    VideoWriteVisibility,
)


class VideoChapterWrite(BaseSchema):
    title: str = Field(min_length=1, max_length=120)
    startsAtSeconds: int = Field(ge=0)


class VideoChapterGet(VideoChapterWrite):
    pass


class VideoCreate(BaseSchema):
    source_asset_id: uuid.UUID
    cover_asset_id: uuid.UUID
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=4000)
    tags: list[str] | None = None
    visibility: VideoWriteVisibility = VideoWriteVisibility.PRIVATE
    status: VideoWriteStatus = VideoWriteStatus.DRAFT
    chapters: list[VideoChapterWrite] = Field(default_factory=list)


class VideoUpdate(BaseSchema):
    source_asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = None
    visibility: VideoWriteVisibility | None = None
    status: VideoWriteStatus | None = None
    chapters: list[VideoChapterWrite] | None = None


class VideoAssetGet(BaseSchema):
    asset_id: uuid.UUID
    attachment_type: AttachmentTypeEnum
    asset_type: AssetTypeEnum
    status: AssetStatusEnum
    mime_type: str | None = None
    original_filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    preview_url: str | None = None
    original_url: str | None = None
    poster_url: str | None = None
    variants: list[AssetVariantGet] = Field(default_factory=list)


class VideoPlaybackSourceGet(BaseSchema):
    id: str
    label: str
    src: str
    mimeType: str
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    bitrate: int | None = Field(default=None, ge=0)
    isOriginal: bool = False


class VideoCardGet(BaseSchema):
    video_id: uuid.UUID
    content_id: uuid.UUID
    content_type: ContentTypeEnum = ContentTypeEnum.VIDEO
    title: str
    description: str
    excerpt: str
    canonical_path: str
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    comments_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    views_count: int = Field(default=0, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    orientation: VideoOrientationEnum | None = None
    processing_status: VideoProcessingStatusEnum
    processing_error: str | None = None
    available_quality_metadata: dict = Field(default_factory=dict)
    user: UserGet
    tags: list[TagGet] = Field(default_factory=list)
    cover: VideoAssetGet | None = None
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool


class VideoGet(VideoCardGet):
    source_asset: VideoAssetGet | None = None
    playback_sources: list[VideoPlaybackSourceGet] = Field(default_factory=list)
    chapters: list[VideoChapterGet] = Field(default_factory=list)
    publish_requested_at: datetime.datetime | None = None
    history_progress: dict | None = None


class VideoEditorGet(VideoGet):
    source_asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None


class VideoRating(BaseSchema):
    video_id: uuid.UUID
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None
