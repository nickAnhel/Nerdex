import datetime
import uuid

from pydantic import Field

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.common.schemas import BaseSchema
from src.moments.enums import MomentWriteStatus, MomentWriteVisibility
from src.tags.schemas import TagGet
from src.users.schemas import UserGet
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum
from src.videos.schemas import VideoAssetGet, VideoPlaybackSourceGet


class MomentCreate(BaseSchema):
    source_asset_id: uuid.UUID
    cover_asset_id: uuid.UUID
    caption: str = Field(default="", max_length=2200)
    tags: list[str] | None = None
    visibility: MomentWriteVisibility = MomentWriteVisibility.PRIVATE
    status: MomentWriteStatus = MomentWriteStatus.DRAFT


class MomentUpdate(BaseSchema):
    source_asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None
    caption: str | None = Field(default=None, max_length=2200)
    tags: list[str] | None = None
    visibility: MomentWriteVisibility | None = None
    status: MomentWriteStatus | None = None


class MomentGet(BaseSchema):
    moment_id: uuid.UUID
    content_id: uuid.UUID
    content_type: ContentTypeEnum = ContentTypeEnum.MOMENT
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    caption: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    publish_requested_at: datetime.datetime | None = None
    comments_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    views_count: int = Field(default=0, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    orientation: VideoOrientationEnum | None = None
    processing_status: VideoProcessingStatusEnum
    processing_error: str | None = None
    available_quality_metadata: dict = Field(default_factory=dict)
    user: UserGet
    tags: list[TagGet] = Field(default_factory=list)
    cover: VideoAssetGet | None = None
    source_asset: VideoAssetGet | None = None
    playback_sources: list[VideoPlaybackSourceGet] = Field(default_factory=list)
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool


class MomentEditorGet(MomentGet):
    source_asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None
