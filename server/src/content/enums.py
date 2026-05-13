from enum import Enum


class ContentTypeEnum(str, Enum):
    POST = "post"
    ARTICLE = "article"
    VIDEO = "video"
    MOMENT = "moment"
    COURSE = "course"


class ContentStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ContentVisibilityEnum(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class ReactionTypeEnum(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    HEART = "heart"
    FIRE = "fire"
    JOY = "joy"
    CRY = "cry"
    THINKING = "thinking"
    EXPLODING_HEAD = "exploding_head"
    CLAP = "clap"
    PRAY = "pray"
