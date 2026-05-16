import uuid
from enum import Enum

from pydantic import Field

from src.common.schemas import BaseSchema
from src.content.schemas import ContentListItemGet
from src.users.schemas import UserGet


class SimilarContentItemGet(BaseSchema):
    content_id: uuid.UUID
    score: float
    reason: str
    content: ContentListItemGet


class SimilarContentListGet(BaseSchema):
    items: list[SimilarContentItemGet] = Field(default_factory=list)
    limit: int = Field(ge=1)


class RecommendedAuthorItemGet(BaseSchema):
    user_id: uuid.UUID
    score: float
    reason: str
    author: UserGet


class RecommendationFeedContentTypeEnum(str, Enum):
    ALL = "all"
    POST = "post"
    ARTICLE = "article"
    VIDEO = "video"
    MOMENT = "moment"


class RecommendationFeedSortEnum(str, Enum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    OLDEST = "oldest"
