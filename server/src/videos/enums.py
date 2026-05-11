from enum import Enum


class VideoOrder(str, Enum):
    ID = "video_id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"


class VideoProfileFilter(str, Enum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    DRAFTS = "drafts"


class VideoWriteStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class VideoWriteVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class VideoOrientationEnum(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"


class VideoProcessingStatusEnum(str, Enum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    METADATA_EXTRACTING = "metadata_extracting"
    TRANSCODING = "transcoding"
    READY = "ready"
    FAILED = "failed"
