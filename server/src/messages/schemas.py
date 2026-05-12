import datetime
import uuid

from pydantic import BaseModel

from src.common.schemas import BaseSchema
from src.users.schemas import UserGet


class MessageCreateWS(BaseModel):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID
    content: str
    reply_to_message_id: uuid.UUID | None = None


class MessageReplyPreview(BaseModel):
    message_id: uuid.UUID
    sender_display_name: str
    content_preview: str
    deleted: bool


class MessageGetWS(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    item_type: str = "message"
    chat_seq: int | None = None
    content: str
    created_at: datetime.datetime
    edited_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    deleted_by: uuid.UUID | None = None
    reply_to_message_id: uuid.UUID | None = None
    reply_preview: MessageReplyPreview | None = None
    username: str
    user_id: uuid.UUID
    avatar_small_url: str | None = None


class MessageUpdateWS(BaseModel):
    message_id: uuid.UUID
    content: str


class MessageDeleteWS(BaseModel):
    message_id: uuid.UUID


class MessageCreate(BaseSchema):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    content: str
    user_id: uuid.UUID
    reply_to_message_id: uuid.UUID | None = None


class MessageGet(MessageCreate):
    message_id: uuid.UUID
    created_at: datetime.datetime
    edited_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    deleted_by: uuid.UUID | None = None
    chat_seq: int | None = None
    reply_preview: MessageReplyPreview | None = None


class MessageGetWithUser(MessageGet):
    user: UserGet


class MessageUpdate(BaseSchema):
    content: str | None = None
