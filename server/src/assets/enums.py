from enum import Enum


class AssetTypeEnum(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"


class AssetStatusEnum(str, Enum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class AssetAccessTypeEnum(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    INHERITED = "inherited"


class AssetVariantStatusEnum(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class AssetVariantTypeEnum(str, Enum):
    ORIGINAL = "original"
    AVATAR_MEDIUM = "avatar_medium"
    AVATAR_SMALL = "avatar_small"
    IMAGE_MEDIUM = "image_medium"
    IMAGE_SMALL = "image_small"
    VIDEO_PREVIEW_ORIGINAL = "video_preview_original"
    VIDEO_PREVIEW_MEDIUM = "video_preview_medium"
    VIDEO_PREVIEW_SMALL = "video_preview_small"
    VIDEO_720P = "video_720p"
    VIDEO_1080P = "video_1080p"


class AttachmentTypeEnum(str, Enum):
    MEDIA = "media"
    FILE = "file"
    COVER = "cover"
    INLINE = "inline"
    VIDEO_SOURCE = "video_source"
    VIDEO_PREVIEW = "video_preview"
    THUMBNAIL = "thumbnail"
