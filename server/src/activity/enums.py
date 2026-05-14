from enum import Enum


class ActivityActionTypeEnum(str, Enum):
    CONTENT_VIEW = "content_view"
    CONTENT_LIKE = "content_like"
    CONTENT_DISLIKE = "content_dislike"
    CONTENT_REACTION_REMOVED = "content_reaction_removed"
    CONTENT_COMMENT = "content_comment"
    USER_FOLLOW = "user_follow"
    USER_UNFOLLOW = "user_unfollow"


class ActivityPeriodEnum(str, Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL_TIME = "all_time"
