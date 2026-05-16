import uuid

from pydantic import Field

from src.common.schemas import BaseSchema
from src.content.schemas import ContentListItemGet


class SimilarContentItemGet(BaseSchema):
    content_id: uuid.UUID
    score: float
    reason: str
    content: ContentListItemGet


class SimilarContentListGet(BaseSchema):
    items: list[SimilarContentItemGet] = Field(default_factory=list)
    limit: int = Field(ge=1)
