from enum import Enum


class MomentWriteStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class MomentWriteVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class MomentOrder(str, Enum):
    ID = "moment_id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"


class MomentProfileFilter(str, Enum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    DRAFTS = "drafts"
