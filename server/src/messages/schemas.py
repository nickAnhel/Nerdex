import datetime
import uuid

from pydantic import BaseModel

from src.common.schemas import BaseSchema
from src.users.schemas import UserGet


class MessageCreateWS(BaseModel):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID
    content: str


class MessageGetWS(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    item_type: str = "message"
    chat_seq: int | None = None
    content: str
    created_at: datetime.datetime
    username: str
    user_id: uuid.UUID
    avatar_small_url: str | None = None


class MessageCreate(BaseSchema):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    content: str
    user_id: uuid.UUID


class MessageGet(MessageCreate):
    message_id: uuid.UUID
    created_at: datetime.datetime
    chat_seq: int | None = None


class MessageGetWithUser(MessageGet):
    user: UserGet


class MessageUpdate(BaseSchema):
    content: str | None = None
