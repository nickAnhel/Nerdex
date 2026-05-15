from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from src.assets.enums import AttachmentTypeEnum, AssetTypeEnum
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum


@dataclass(slots=True)
class PlannedUser:
    user_id: uuid.UUID
    username: str
    display_name: str
    hashed_password: str
    bio: str
    links: list[dict]
    is_admin: bool
    created_at: dt.datetime
    interests: dict[str, float]
    preferred_content_types: dict[str, float]
    expected_tags: list[str]
    role: str
    is_featured: bool
    presentation_note_en: str
    avatar_asset_id: uuid.UUID | None = None


@dataclass(slots=True)
class PlannedAssetVariant:
    asset_variant_id: uuid.UUID
    asset_variant_type: str
    storage_bucket: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    bitrate: int | None = None
    checksum_sha256: str | None = None
    is_primary: bool = True
    status: str = "ready"
    variant_metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class PlannedAsset:
    asset_id: uuid.UUID
    owner_id: uuid.UUID
    asset_type: AssetTypeEnum
    original_filename: str
    original_extension: str
    detected_mime_type: str
    declared_mime_type: str
    size_bytes: int
    status: str
    access_type: str
    created_at: dt.datetime
    updated_at: dt.datetime
    asset_metadata: dict
    variants: list[PlannedAssetVariant]


@dataclass(slots=True)
class PlannedContent:
    content_id: uuid.UUID
    author_id: uuid.UUID
    content_type: ContentTypeEnum
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    title: str
    excerpt: str
    created_at: dt.datetime
    updated_at: dt.datetime
    published_at: dt.datetime | None
    content_metadata: dict
    topic: str
    tags: list[str]
    media_asset_ids: list[uuid.UUID]
    cover_asset_id: uuid.UUID | None
    file_asset_ids: list[uuid.UUID]
    body_text: str | None = None
    body_markdown: str | None = None
    slug: str | None = None
    word_count: int | None = None
    reading_time_minutes: int | None = None
    toc: list[dict] | None = None
    description: str | None = None
    chapters: list[dict] | None = None
    caption: str | None = None
    video_source_asset_id: uuid.UUID | None = None
    playback_duration_seconds: int | None = None
    playback_width: int | None = None
    playback_height: int | None = None
    playback_orientation: VideoOrientationEnum | None = None
    playback_status: VideoProcessingStatusEnum | None = None


@dataclass(slots=True)
class PlannedSubscription:
    subscriber_id: uuid.UUID
    subscribed_id: uuid.UUID


@dataclass(slots=True)
class PlannedContentReaction:
    content_id: uuid.UUID
    user_id: uuid.UUID
    reaction_type: ReactionTypeEnum
    created_at: dt.datetime


@dataclass(slots=True)
class PlannedComment:
    comment_id: uuid.UUID
    content_id: uuid.UUID
    author_id: uuid.UUID
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    reply_to_comment_id: uuid.UUID | None
    depth: int
    body_text: str
    created_at: dt.datetime
    updated_at: dt.datetime


@dataclass(slots=True)
class PlannedCommentReaction:
    comment_id: uuid.UUID
    user_id: uuid.UUID
    reaction_type: ReactionTypeEnum
    created_at: dt.datetime


@dataclass(slots=True)
class PlannedViewSession:
    view_session_id: uuid.UUID
    content_id: uuid.UUID
    viewer_id: uuid.UUID
    started_at: dt.datetime
    last_seen_at: dt.datetime
    last_position_seconds: int
    max_position_seconds: int
    watched_seconds: int
    progress_percent: int
    is_counted: bool
    counted_at: dt.datetime | None
    counted_date: dt.date | None
    source: str
    view_metadata: dict


@dataclass(slots=True)
class PlannedActivityEvent:
    activity_event_id: uuid.UUID
    user_id: uuid.UUID
    action_type: str
    content_id: uuid.UUID | None
    target_user_id: uuid.UUID | None
    comment_id: uuid.UUID | None
    content_type: ContentTypeEnum | None
    created_at: dt.datetime
    event_metadata: dict


@dataclass(slots=True)
class PlannedChat:
    chat_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    chat_type: str
    is_private: bool
    direct_key: str | None


@dataclass(slots=True)
class PlannedMembership:
    chat_id: uuid.UUID
    user_id: uuid.UUID
    role: str


@dataclass(slots=True)
class PlannedMessage:
    message_id: uuid.UUID
    client_message_id: uuid.UUID
    chat_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    created_at: dt.datetime
    reply_to_message_id: uuid.UUID | None


@dataclass(slots=True)
class PlannedMessageReaction:
    message_id: uuid.UUID
    user_id: uuid.UUID
    reaction_type: ReactionTypeEnum
    created_at: dt.datetime


@dataclass(slots=True)
class PlannedMessageSharedContent:
    message_id: uuid.UUID
    content_id: uuid.UUID


@dataclass(slots=True)
class PlannedMessageAsset:
    message_id: uuid.UUID
    asset_id: uuid.UUID
    sort_order: int


@dataclass(slots=True)
class PlannedEvent:
    event_id: uuid.UUID
    event_type: str
    created_at: dt.datetime
    user_id: uuid.UUID
    altered_user_id: uuid.UUID | None
    chat_id: uuid.UUID


@dataclass(slots=True)
class PlannedTimelineItem:
    chat_id: uuid.UUID
    chat_seq: int
    item_type: str
    message_id: uuid.UUID | None
    event_id: uuid.UUID | None
