from enum import Enum


class SearchTypeEnum(str, Enum):
    ALL = "all"
    POST = "post"
    VIDEO = "video"
    ARTICLE = "article"
    MOMENT = "moment"
    AUTHOR = "author"


class SearchSortEnum(str, Enum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    OLDEST = "oldest"
