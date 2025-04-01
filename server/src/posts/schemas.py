import uuid
import datetime

from pydantic import Field

from src.schemas import BaseSchema


class PostCreate(BaseSchema):
    content: str = Field(max_length=8192)


class PostGet(PostCreate):
    post_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime.datetime


class PostUpdate(BaseSchema):
    content: str | None = None
