from enum import Enum


class SearchTypeEnum(str, Enum):
    ALL = "all"
    POST = "post"
    VIDEO = "video"
    ARTICLE = "article"
    MOMENT = "moment"
    AUTHOR = "author"


class SearchContentTypeEnum(str, Enum):
    ALL = "all"
    POST = "post"
    VIDEO = "video"
    ARTICLE = "article"
    MOMENT = "moment"


class SearchSortEnum(str, Enum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    OLDEST = "oldest"


class SearchPopularPeriodEnum(str, Enum):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL_TIME = "all_time"
