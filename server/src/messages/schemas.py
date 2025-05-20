import datetime
import uuid

from pydantic import BaseModel

from src.schemas import BaseSchema
from src.users.schemas import UserGet


class MessageCreateWS(BaseModel):
    content: str
    created_at: datetime.datetime


class MessageGetWS(MessageCreateWS):
    message_id: uuid.UUID
    username: str
    user_id: uuid.UUID


class MessageCreate(BaseSchema):
    chat_id: uuid.UUID
    content: str
    user_id: uuid.UUID
    created_at: datetime.datetime


class MessageGet(MessageCreate):
    message_id: uuid.UUID


class MessageGetWithUser(MessageGet):
    user: UserGet


class MessageUpdate(BaseSchema):
    content: str | None = None
