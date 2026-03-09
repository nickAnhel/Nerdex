from enum import Enum


class PostOrder(str, Enum):
    ID = "post_id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"


class PostWriteStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class PostWriteVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class PostProfileFilter(str, Enum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    DRAFTS = "drafts"
