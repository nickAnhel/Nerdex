from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.common.schemas import BaseSchema
from src.content.schemas import ContentListItemGet
from src.search.enums import SearchSortEnum, SearchTypeEnum
from src.users.schemas import UserGet


class SearchResultItemGet(BaseSchema):
    result_type: Literal["content", "author"]
    content: ContentListItemGet | None = None
    author: UserGet | None = None
    score: float = Field(ge=0)


class SearchListGet(BaseSchema):
    items: list[SearchResultItemGet] = Field(default_factory=list)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    has_more: bool


class SearchParams(BaseSchema):
    q: str = Field(min_length=1, max_length=120)
    type: SearchTypeEnum = SearchTypeEnum.ALL
    sort: SearchSortEnum = SearchSortEnum.RELEVANCE
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
