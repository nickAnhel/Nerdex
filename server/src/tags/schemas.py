import uuid

from src.common.schemas import BaseSchema


class TagGet(BaseSchema):
    tag_id: uuid.UUID
    slug: str
