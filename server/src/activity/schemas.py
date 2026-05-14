import datetime
import typing as tp
import uuid

from pydantic import Field

from src.activity.enums import ActivityActionTypeEnum
from src.common.schemas import BaseSchema
from src.content.enums import ContentTypeEnum
from src.content.schemas import ContentListItemGet
from src.users.schemas import UserGet


class ActivityCommentPreviewGet(BaseSchema):
    comment_id: uuid.UUID
    body_preview: str | None = None
    deleted_at: datetime.datetime | None = None
    created_at: datetime.datetime | None = None


class ActivityEventGet(BaseSchema):
    activity_event_id: uuid.UUID
    action_type: ActivityActionTypeEnum
    created_at: datetime.datetime
    content_type: ContentTypeEnum | None = None
    content: ContentListItemGet | None = None
    target_user: UserGet | None = None
    comment: ActivityCommentPreviewGet | None = None
    metadata: dict[str, tp.Any] = Field(default_factory=dict)


class ActivityEventListGet(BaseSchema):
    items: list[ActivityEventGet]
    offset: int = Field(ge=0)
    limit: int = Field(ge=0)
    has_more: bool
