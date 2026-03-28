from __future__ import annotations

import datetime
import uuid

from pydantic import Field

from src.common.schemas import BaseSchema
from src.content.enums import ReactionTypeEnum
from src.users.schemas import UserAvatarGet, Username

COMMENT_BODY_MAX_LENGTH = 2048
DEFAULT_COMMENTS_LIMIT = 20
MAX_COMMENTS_LIMIT = 100


class CommentAuthorGet(BaseSchema):
    user_id: uuid.UUID
    username: Username
    avatar: UserAvatarGet | None = None


class CommentRefGet(BaseSchema):
    comment_id: uuid.UUID
    is_deleted: bool


class CommentCreate(BaseSchema):
    body_text: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LENGTH)


class CommentUpdate(BaseSchema):
    body_text: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LENGTH)


class CommentGet(BaseSchema):
    comment_id: uuid.UUID
    content_id: uuid.UUID
    author: CommentAuthorGet | None = None
    parent_comment_id: uuid.UUID | None = None
    root_comment_id: uuid.UUID | None = None
    reply_to_comment_id: uuid.UUID | None = None
    depth: int = Field(ge=0, le=2)
    body_text: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    replies_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool
    is_deleted: bool
    reply_to_comment_depth: int | None = Field(default=None, ge=0, le=2)
    reply_to_username: str | None = None
    reply_to_comment_ref: CommentRefGet | None = None


class CommentReactionGet(BaseSchema):
    comment_id: uuid.UUID
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None


class CommentPageGet(BaseSchema):
    items: list[CommentGet]
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)
    has_more: bool


class CommentsPageGet(CommentPageGet):
    pass


class RepliesPageGet(CommentPageGet):
    pass
