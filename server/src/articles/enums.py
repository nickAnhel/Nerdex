from enum import Enum


class ArticleOrder(str, Enum):
    ID = "article_id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"


class ArticleWriteStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ArticleWriteVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class ArticleProfileFilter(str, Enum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    DRAFTS = "drafts"
