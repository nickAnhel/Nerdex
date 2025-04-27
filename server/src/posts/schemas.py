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
    likes: int = Field(ge=0)
    dislikes: int = Field(ge=0)


class PostUpdate(BaseSchema):
    content: str | None = None


class PostRating(BaseSchema):
    post_id: uuid.UUID
    likes: int = Field(ge=0)
    dislikes: int = Field(ge=0)
