from enum import Enum


class ContentOrder(str, Enum):
    ID = "content_id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"
